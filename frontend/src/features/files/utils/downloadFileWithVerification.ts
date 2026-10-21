/**
 * Phase 260.3.G — verified file-download orchestrator for the browser.
 *
 * The `download` action returns a presigned S3 URL plus the
 * platform-stored SHA-256. This function:
 *
 *   1. Calls ``fileService.getDownloadPayload`` to get URL + expected
 *      hash.
 *   2. Fetches the bytes from S3 (via injectable transport so tests
 *      can drive deterministic fakes; production uses
 *      :func:`fetchBlobFromS3`).
 *   3. Verifies SHA-256 of the downloaded blob.
 *   4. On mismatch:
 *      - reports the actual hash to
 *        ``POST /files/{id}/download/checksum-mismatch/`` (best-effort;
 *        the audit row lands even if the caller's catch swallows the
 *        ``ChecksumMismatchError``),
 *      - throws :class:`ChecksumMismatchError` so the UI never hands
 *        a corrupted blob to the user.
 *   5. On match — returns the blob with ``status='matched'``.
 *   6. When the platform has no expected hash (older files) — returns
 *      the blob with ``status='skipped'`` so the caller's policy can
 *      decide whether to allow or block.
 */

import { debugLogger } from '../../../shared/utils/debugLogger';
import { fileService } from '../services/fileService';
import {
  computeBlobSha256,
  shaEqualsConstantTime,
} from './downloadChecksumVerify';

/**
 * Phase 260.3.G.R1 GAP-B — memory guard for browser-side verification.
 *
 * ``crypto.subtle.digest('SHA-256', …)`` requires an
 * ``ArrayBuffer`` (non-streaming in the WebCrypto spec), and
 * ``Blob.arrayBuffer()`` allocates a contiguous copy — so verifying
 * a 4 GiB file allocates ~8 GiB of RAM peak (Blob + ArrayBuffer)
 * which OOMs the browser tab.
 *
 * Files larger than this threshold skip in-browser verification AND
 * fall through to the legacy ``openPresignedDownloadUrl`` flow so the
 * native browser download (with its disk-streaming + progress UI)
 * still works. The SDK has no such limit because Python's hashlib
 * supports streaming and httpx can stream chunks to a hash-and-write
 * pipeline.
 *
 * Default 512 MiB — generous enough that 99 % of dataset uploads
 * verify, conservative enough that a typical browser tab (~2 GiB
 * heap) never OOMs from the 2× allocation.
 */
export const MAX_BROWSER_VERIFICATION_SIZE_BYTES = 512 * 1024 * 1024;

export type S3FetchFn = (url: string) => Promise<Blob>;

export interface DownloadFileResult {
  status: 'matched' | 'skipped';
  blob: Blob;
  filename: string;
  expected: string | null;
  actual: string;
  /**
   * When ``status === 'skipped'``, why we skipped. Drives the
   * FileListPage fallback: ``too-large-for-browser-verification``
   * routes through the legacy presign-and-navigate path so the
   * user can still download the file via the native browser flow.
   */
  skipReason?:
    | 'no-expected-hash'
    | 'malformed-expected-hash'
    | 'too-large-for-browser-verification';
}

export class FileTooLargeForVerificationError extends Error {
  readonly fileId: string;
  readonly filename: string;
  readonly size: number;
  readonly maxSize: number;
  readonly downloadUrl: string;

  constructor(args: {
    fileId: string;
    filename: string;
    size: number;
    maxSize: number;
    downloadUrl: string;
  }) {
    super(
      `File ${args.filename} (${args.size} bytes) exceeds the in-browser ` +
        `verification limit of ${args.maxSize} bytes. Use the SDK for ` +
        `verified downloads of files this large, or fall back to the ` +
        `unverified browser-native download path.`
    );
    this.name = 'FileTooLargeForVerificationError';
    this.fileId = args.fileId;
    this.filename = args.filename;
    this.size = args.size;
    this.maxSize = args.maxSize;
    this.downloadUrl = args.downloadUrl;
  }
}

export class ChecksumMismatchError extends Error {
  readonly fileId: string;
  readonly expected: string;
  readonly actual: string;

  constructor(args: { fileId: string; expected: string; actual: string }) {
    super(
      `Downloaded file SHA-256 does not match the platform-stored hash ` +
        `for file ${args.fileId} (expected ${args.expected.slice(0, 16)}…, ` +
        `got ${args.actual.slice(0, 16)}…). Refusing to deliver corrupted ` +
        `bytes to the user.`
    );
    this.name = 'ChecksumMismatchError';
    this.fileId = args.fileId;
    this.expected = args.expected;
    this.actual = args.actual;
  }
}

/**
 * Production S3 fetch transport. Cross-origin XHR/fetch must allow
 * ``no-cors=false`` (the default) so the response body is accessible
 * to JS. The presigned URL bakes in the auth signature; we don't
 * need to send credentials.
 */
export const fetchBlobFromS3: S3FetchFn = async (url) => {
  const response = await fetch(url, {
    method: 'GET',
    // Don't send cookies / credentials to S3 — the presigned URL is
    // the auth surface and adding credentials triggers stricter CORS.
    credentials: 'omit',
  });
  if (!response.ok) {
    throw new Error(`S3 GET failed with status ${response.status}: ${response.statusText}`);
  }
  return await response.blob();
};

interface DownloadOptions {
  /** Injectable for testability; defaults to :func:`fetchBlobFromS3`. */
  s3Fetch?: S3FetchFn;
  /**
   * Override the in-browser verification size cap. Tests use this to
   * exercise the size-guard branch without allocating real GiB.
   */
  maxVerificationSizeBytes?: number;
  /**
   * Optional file size (typically from the catalog row's ``size``
   * field). When provided, the orchestrator can refuse-or-fall-back
   * BEFORE allocating a multi-GiB Blob. When omitted, the cap is
   * checked against the Blob.size after fetch — still memory-safe
   * because the next step (``arrayBuffer``) is what doubles RAM.
   */
  fileSizeBytes?: number;
}

/**
 * Download the file, verify the SHA-256, and either return the blob
 * (matched / skipped) or throw :class:`ChecksumMismatchError` after
 * recording the audit (mismatched).
 */
export async function downloadFileWithVerification(
  fileId: string,
  options: DownloadOptions = {}
): Promise<DownloadFileResult> {
  const s3Fetch = options.s3Fetch ?? fetchBlobFromS3;
  const sizeCap = options.maxVerificationSizeBytes ?? MAX_BROWSER_VERIFICATION_SIZE_BYTES;

  const payload = await fileService.getDownloadPayload(fileId);

  // Phase 260.3.G.R1 GAP-B fix: refuse to begin a verified download for
  // files we know up-front are too large to safely hash in the browser
  // (would OOM the tab on the 2× allocation Blob + ArrayBuffer).
  // Surface a typed error so the caller can fall back to the legacy
  // unverified navigate path; we DO NOT silently start fetching a
  // multi-GiB blob and then "skip" verification mid-download.
  if (
    options.fileSizeBytes !== undefined &&
    options.fileSizeBytes > sizeCap
  ) {
    throw new FileTooLargeForVerificationError({
      fileId,
      filename: payload.filename,
      size: options.fileSizeBytes,
      maxSize: sizeCap,
      downloadUrl: payload.download_url,
    });
  }

  const blob = await s3Fetch(payload.download_url);

  const expected = payload.content_sha256 ?? null;
  if (expected === null || !/^[0-9a-fA-F]{64}$/.test(expected)) {
    // No expected hash — older file, or platform didn't capture one.
    return {
      status: 'skipped',
      blob,
      filename: payload.filename,
      expected: null,
      actual: '',
      skipReason:
        expected === null ? 'no-expected-hash' : 'malformed-expected-hash',
    };
  }

  // Defence-in-depth: if the catalog row was wrong about ``size`` (or
  // the caller didn't pass it), the second guard catches the actual
  // blob size before we double-allocate via ``arrayBuffer``.
  if (blob.size > sizeCap) {
    return {
      status: 'skipped',
      blob,
      filename: payload.filename,
      expected,
      actual: '',
      skipReason: 'too-large-for-browser-verification',
    };
  }

  const actual = await computeBlobSha256(blob);
  if (shaEqualsConstantTime(actual, expected)) {
    return {
      status: 'matched',
      blob,
      filename: payload.filename,
      expected: expected.toLowerCase(),
      actual,
    };
  }

  // MISMATCH — defence-in-depth audit + refuse-to-deliver.
  // Best-effort: even if the report fails, we MUST still throw so the
  // caller cannot ignore the corruption.
  try {
    await fileService.reportChecksumMismatch(fileId, actual);
  } catch (reportErr) {
    // Surface to console for production observability; do NOT silently
    // suppress the throw below.
    debugLogger.error('checksum_mismatch_report_failed', { file_id: fileId, error: String(reportErr) });
  }
  throw new ChecksumMismatchError({
    fileId,
    expected: expected.toLowerCase(),
    actual,
  });
}
