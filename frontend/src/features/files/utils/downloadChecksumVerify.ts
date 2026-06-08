/**
 * Phase 260.3.G.1 — SHA-256 verification of downloaded file content
 * against the platform-stored ``File.content_sha256``.
 *
 * Design notes
 * ------------
 * - **Streaming-safe digest.** ``crypto.subtle.digest`` consumes the
 *   blob's ``ArrayBuffer`` in a single pass; we don't double-buffer
 *   the bytes. For a 4 GiB file this still requires loading the
 *   whole content into memory once because ``digest`` is non-streaming
 *   in the WebCrypto spec — that's a browser limitation, not ours,
 *   and is acceptable since ``downloadFileWithVerification`` reads the
 *   blob once anyway. For chunked verification mid-multipart-upload
 *   we use the per-part ETag from S3 (Phase 260.3.F).
 *
 * - **Constant-time comparison.** ``shaEqualsConstantTime`` walks the
 *   FULL string regardless of where the first diff sits. SHA-256 is
 *   a fixed 64-hex-char string, so the cost of "constant-time" is
 *   bounded and trivial; we don't return early on length mismatch
 *   beyond the upfront sanity check (length differences past 64
 *   chars indicate a bug in the caller, not a side-channel target).
 *
 * - **Skip on null expected.** Older files predating Phase 260.3.G
 *   have ``content_sha256 = NULL``; we report ``skipped`` rather
 *   than ``matched`` so dashboards can distinguish "verified clean"
 *   from "couldn't verify". The caller decides whether to allow the
 *   download in that case.
 */

const SHA256_HEX_RE = /^[0-9a-fA-F]{64}$/;

export type ChecksumVerificationStatus = 'matched' | 'mismatched' | 'skipped';

export interface ChecksumVerificationResult {
  status: ChecksumVerificationStatus;
  /** Expected hash from the server (lowercase hex), or null when skipped. */
  expected?: string | null;
  /** Computed hash from the downloaded blob, or null when skipped. */
  actual?: string | null;
  /** When ``skipped``, the reason — drives dashboard breakdowns. */
  reason?: 'no-expected-hash' | 'malformed-expected-hash';
}

/**
 * Compute the lowercase hex SHA-256 of ``blob`` using WebCrypto.
 */
export async function computeBlobSha256(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Constant-time hex SHA-256 equality. Returns ``false`` on any
 * non-string input, length mismatch, or per-character difference;
 * NEVER throws.
 *
 * The "constant-time" guarantee here covers the per-character XOR
 * loop only — the upfront type / length checks are intentionally NOT
 * constant-time because their failure mode (a malformed input from
 * either side) is a programming bug, not a side-channel target.
 */
export function shaEqualsConstantTime(a: string, b: string): boolean {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  if (a.length === 0 || b.length === 0) return false;
  if (a.length !== b.length) return false;
  const lo = a.toLowerCase();
  const ro = b.toLowerCase();
  let diff = 0;
  for (let i = 0; i < lo.length; i += 1) {
    diff |= lo.charCodeAt(i) ^ ro.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Verify the SHA-256 of ``blob`` against the server-reported
 * ``expected`` hash. Returns a structured result; never throws.
 */
export async function verifyBlobChecksum(
  blob: Blob,
  expected: string | null | undefined
): Promise<ChecksumVerificationResult> {
  if (expected === null || expected === undefined) {
    return { status: 'skipped', expected: null, actual: null, reason: 'no-expected-hash' };
  }
  if (typeof expected !== 'string' || !SHA256_HEX_RE.test(expected)) {
    return {
      status: 'skipped',
      expected: null,
      actual: null,
      reason: 'malformed-expected-hash',
    };
  }
  const actual = await computeBlobSha256(blob);
  const expectedLower = expected.toLowerCase();
  if (shaEqualsConstantTime(actual, expectedLower)) {
    return { status: 'matched', expected: expectedLower, actual };
  }
  return { status: 'mismatched', expected: expectedLower, actual };
}
