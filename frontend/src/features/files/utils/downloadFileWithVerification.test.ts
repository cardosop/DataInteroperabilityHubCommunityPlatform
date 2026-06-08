/**
 * downloadFileWithVerification tests — Phase 260.3.G full-flow.
 *
 * Behavioural tests for the orchestrator that:
 *   1. fetches the presigned URL + expected SHA-256 via fileService,
 *   2. downloads the blob from S3 via fetch (DI'd for testability),
 *   3. verifies the SHA-256 of the downloaded bytes,
 *   4. on mismatch — calls ``fileService.reportChecksumMismatch`` AND
 *      throws ``ChecksumMismatchError`` (the caller must NOT deliver
 *      the corrupted blob to the user),
 *   5. on match — returns the blob,
 *   6. on no-expected-hash (older files) — returns the blob with the
 *      ``status='skipped'`` flag in the result so callers can branch
 *      on policy (some surfaces require verification; others tolerate
 *      pre-260.3.G files).
 *
 * Boundary mocks: HTTP boundary (apiClient) + the S3 fetch transport
 * are injected for the test. Everything else (the Web Crypto digest,
 * the hex compare, the orchestration) is real.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import {
  ChecksumMismatchError,
  FileTooLargeForVerificationError,
  MAX_BROWSER_VERIFICATION_SIZE_BYTES,
  downloadFileWithVerification,
  type S3FetchFn,
} from './downloadFileWithVerification';

const ABC_SHA256 = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

function setupHttpMocks(opts: {
  contentSha256?: string | null;
  filename?: string;
  recordSpy?: (body: unknown) => void;
}) {
  const httpMock = vi.mocked(apiClient.getClient());
  vi.mocked(httpMock.get).mockImplementation(((url: string) => {
    if (url.match(/files\/[^/]+\/download\/$/)) {
      return Promise.resolve({
        data: {
          download_url: 'https://s3.example.com/presigned',
          expires_in: 3600,
          filename: opts.filename ?? 'data.csv',
          content_sha256: opts.contentSha256 ?? null,
        },
      }) as never;
    }
    throw new Error(`unexpected GET ${url}`);
  }) as never);
  vi.mocked(httpMock.post).mockImplementation(((url: string, body?: unknown) => {
    if (url.match(/files\/[^/]+\/download\/checksum-mismatch\/$/)) {
      opts.recordSpy?.(body);
      return Promise.resolve({ data: { recorded: true } }) as never;
    }
    throw new Error(`unexpected POST ${url}`);
  }) as never);
}

describe('downloadFileWithVerification — happy path', () => {
  it('returns the blob with status="matched" when SHA-256 agrees', async () => {
    setupHttpMocks({ contentSha256: ABC_SHA256 });
    const fakeFetch: S3FetchFn = async () =>
      new Blob([new TextEncoder().encode('abc')]);
    const result = await downloadFileWithVerification('file-1', { s3Fetch: fakeFetch });
    expect(result.status).toBe('matched');
    expect(result.blob).toBeInstanceOf(Blob);
    expect(result.filename).toBe('data.csv');
  });

  it('skips verification when content_sha256 is null', async () => {
    setupHttpMocks({ contentSha256: null });
    const fakeFetch: S3FetchFn = async () => new Blob([new Uint8Array(32)]);
    const result = await downloadFileWithVerification('file-old', { s3Fetch: fakeFetch });
    expect(result.status).toBe('skipped');
    expect(result.blob).toBeInstanceOf(Blob);
  });
});

describe('downloadFileWithVerification — mismatch path', () => {
  it('reports the mismatch via API AND throws ChecksumMismatchError', async () => {
    let reportedBody: unknown = null;
    setupHttpMocks({
      contentSha256: ABC_SHA256,
      recordSpy: (b) => {
        reportedBody = b;
      },
    });
    // Tampered: hashing this gives a different SHA-256 than ABC_SHA256.
    const fakeFetch: S3FetchFn = async () =>
      new Blob([new TextEncoder().encode('abd')]);

    await expect(
      downloadFileWithVerification('file-mismatch', { s3Fetch: fakeFetch })
    ).rejects.toBeInstanceOf(ChecksumMismatchError);

    // The HTTP report MUST have been sent BEFORE the throw so the audit
    // row is durable even if the caller's catch swallows the error.
    expect(reportedBody).not.toBeNull();
    const body = reportedBody as { actual_sha256?: string };
    expect(body.actual_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(body.actual_sha256).not.toBe(ABC_SHA256);
  });

  it('attaches expected + actual on the thrown error for caller diagnostics', async () => {
    setupHttpMocks({ contentSha256: ABC_SHA256 });
    const fakeFetch: S3FetchFn = async () =>
      new Blob([new TextEncoder().encode('abd')]);
    try {
      await downloadFileWithVerification('file-mismatch', { s3Fetch: fakeFetch });
      throw new Error('expected ChecksumMismatchError');
    } catch (e) {
      expect(e).toBeInstanceOf(ChecksumMismatchError);
      const err = e as ChecksumMismatchError;
      expect(err.expected).toBe(ABC_SHA256);
      expect(err.actual).toMatch(/^[0-9a-f]{64}$/);
      expect(err.fileId).toBe('file-mismatch');
    }
  });

  it('still throws even if the mismatch-report API itself fails', async () => {
    // Defence-in-depth: if the audit report fails (network blip), we
    // must still refuse to deliver the corrupted blob to the user.
    // Production logs the report failure via ``console.error`` for
    // observability; this test deliberately exercises that path, so
    // silence the log to avoid noise while still asserting the
    // ChecksumMismatchError is raised.
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const httpMock = vi.mocked(apiClient.getClient());
      vi.mocked(httpMock.get).mockResolvedValue({
        data: {
          download_url: 'https://s3.example.com/presigned',
          expires_in: 3600,
          filename: 'x.csv',
          content_sha256: ABC_SHA256,
        },
      } as never);
      vi.mocked(httpMock.post).mockRejectedValue(new Error('audit endpoint 503'));
      const fakeFetch: S3FetchFn = async () =>
        new Blob([new TextEncoder().encode('abd')]);
      await expect(
        downloadFileWithVerification('file-mismatch', { s3Fetch: fakeFetch })
      ).rejects.toBeInstanceOf(ChecksumMismatchError);
      // The console.error path is load-bearing: it MUST fire so the
      // production observability hook is exercised.
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('Failed to report checksum mismatch for file-mismatch'),
        expect.any(Error),
      );
    } finally {
      consoleErrorSpy.mockRestore();
    }
  });
});

describe('downloadFileWithVerification — GAP-B size guard (memory protection)', () => {
  it('exposes a sane default size cap (512 MiB)', () => {
    expect(MAX_BROWSER_VERIFICATION_SIZE_BYTES).toBe(512 * 1024 * 1024);
  });

  it('throws FileTooLargeForVerificationError BEFORE fetching when fileSizeBytes exceeds the cap', async () => {
    setupHttpMocks({ contentSha256: ABC_SHA256 });
    let fetchFired = false;
    const fakeFetch: S3FetchFn = async () => {
      fetchFired = true;
      return new Blob([new Uint8Array(0)]);
    };
    await expect(
      downloadFileWithVerification('big-file', {
        s3Fetch: fakeFetch,
        fileSizeBytes: 600 * 1024 * 1024, // 600 MiB > 512 MiB cap
        maxVerificationSizeBytes: 512 * 1024 * 1024,
      })
    ).rejects.toBeInstanceOf(FileTooLargeForVerificationError);
    expect(fetchFired).toBe(false);
  });

  it('attaches downloadUrl to FileTooLargeForVerificationError so the caller can fall back', async () => {
    setupHttpMocks({ contentSha256: ABC_SHA256 });
    try {
      await downloadFileWithVerification('big-file', {
        fileSizeBytes: 1_000_000_000,
        maxVerificationSizeBytes: 100,
      });
      throw new Error('expected FileTooLargeForVerificationError');
    } catch (e) {
      expect(e).toBeInstanceOf(FileTooLargeForVerificationError);
      const err = e as FileTooLargeForVerificationError;
      expect(err.downloadUrl).toBe('https://s3.example.com/presigned');
      expect(err.size).toBe(1_000_000_000);
      expect(err.maxSize).toBe(100);
    }
  });

  it('post-fetch: returns status="skipped" with too-large-for-browser-verification reason when the catalog under-reported size', async () => {
    setupHttpMocks({ contentSha256: ABC_SHA256 });
    // Catalog said small, but blob is actually big.
    const bigBlob = new Blob([new Uint8Array(2048)]);
    const fakeFetch: S3FetchFn = async () => bigBlob;
    const result = await downloadFileWithVerification('mis-sized', {
      s3Fetch: fakeFetch,
      maxVerificationSizeBytes: 1024,
    });
    expect(result.status).toBe('skipped');
    expect(result.skipReason).toBe('too-large-for-browser-verification');
    expect(result.expected).toBe(ABC_SHA256);
  });

  it('does NOT short-circuit when fileSizeBytes is exactly at the cap', async () => {
    setupHttpMocks({ contentSha256: ABC_SHA256 });
    const fakeFetch: S3FetchFn = async () =>
      new Blob([new TextEncoder().encode('abc')]);
    const result = await downloadFileWithVerification('boundary', {
      s3Fetch: fakeFetch,
      fileSizeBytes: 1024,
      maxVerificationSizeBytes: 1024,
    });
    // 1024 <= 1024 — verification proceeds.
    expect(result.status).toBe('matched');
  });
});

describe('downloadFileWithVerification — skip-reason on missing/malformed expected', () => {
  it('skipped on null expected reports skipReason=no-expected-hash', async () => {
    setupHttpMocks({ contentSha256: null });
    const fakeFetch: S3FetchFn = async () => new Blob([new Uint8Array(8)]);
    const result = await downloadFileWithVerification('old-file', {
      s3Fetch: fakeFetch,
    });
    expect(result.status).toBe('skipped');
    expect(result.skipReason).toBe('no-expected-hash');
  });

  it('skipped on malformed expected reports skipReason=malformed-expected-hash', async () => {
    setupHttpMocks({ contentSha256: 'not-a-real-sha' });
    const fakeFetch: S3FetchFn = async () => new Blob([new Uint8Array(8)]);
    const result = await downloadFileWithVerification('bad-meta', {
      s3Fetch: fakeFetch,
    });
    expect(result.status).toBe('skipped');
    expect(result.skipReason).toBe('malformed-expected-hash');
  });
});

describe('downloadFileWithVerification — fetch failures', () => {
  it('propagates a fetch failure without ever reporting a mismatch', async () => {
    let reportFired = false;
    setupHttpMocks({
      contentSha256: ABC_SHA256,
      recordSpy: () => {
        reportFired = true;
      },
    });
    const fakeFetch: S3FetchFn = async () => {
      throw new Error('S3 GET 403 SignatureDoesNotMatch');
    };
    await expect(
      downloadFileWithVerification('file-1', { s3Fetch: fakeFetch })
    ).rejects.toThrow(/SignatureDoesNotMatch/);
    expect(reportFired).toBe(false);
  });
});
