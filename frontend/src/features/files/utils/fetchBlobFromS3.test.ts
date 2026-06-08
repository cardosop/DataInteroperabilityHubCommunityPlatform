/**
 * Phase 260.3.G.R1 GAP-E — production fetchBlobFromS3 transport tests.
 *
 * The unit tests for the orchestrator inject a fake :type:`S3FetchFn`
 * for determinism — but the production transport ``fetchBlobFromS3``
 * itself (uses native ``fetch`` + ``credentials: 'omit'``) had no
 * direct coverage. These tests pin the contract:
 *
 *   - 200 → resolves with the response Blob
 *   - 4xx / 5xx → rejects with a diagnostic carrying the status
 *   - omit-credentials → no cookies sent to the presigned URL
 *
 * Implementation: ``vi.stubGlobal('fetch', …)`` with a deterministic
 * ``Response`` builder. No production code mocked; real
 * ``fetchBlobFromS3`` runs against a controllable fetch.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchBlobFromS3 } from './downloadFileWithVerification';

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function makeResponse(opts: {
  status: number;
  statusText?: string;
  body?: BodyInit | null;
}): Response {
  return new Response(opts.body ?? null, {
    status: opts.status,
    statusText: opts.statusText ?? '',
  });
}

describe('fetchBlobFromS3', () => {
  it('resolves with the response body as a Blob on 200', async () => {
    fetchMock.mockResolvedValueOnce(
      makeResponse({ status: 200, body: 'hello s3' })
    );
    const blob = await fetchBlobFromS3('https://s3.example.com/presigned');
    expect(blob).toBeInstanceOf(Blob);
    expect(await blob.text()).toBe('hello s3');
  });

  it('passes credentials: "omit" so cookies are not sent to the presigned URL', async () => {
    fetchMock.mockResolvedValueOnce(makeResponse({ status: 200 }));
    await fetchBlobFromS3('https://s3.example.com/x');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init).toMatchObject({ method: 'GET', credentials: 'omit' });
  });

  it('rejects with status + statusText on 4xx', async () => {
    fetchMock.mockResolvedValueOnce(
      makeResponse({ status: 403, statusText: 'Forbidden' })
    );
    await expect(fetchBlobFromS3('https://s3.example.com/forbidden')).rejects.toThrow(
      /403/
    );
  });

  it('rejects with status + statusText on 5xx', async () => {
    fetchMock.mockResolvedValueOnce(
      makeResponse({ status: 500, statusText: 'Internal Server Error' })
    );
    await expect(fetchBlobFromS3('https://s3.example.com/500')).rejects.toThrow(
      /500/
    );
  });

  it('propagates fetch network errors as-is', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(fetchBlobFromS3('https://s3.example.com/dead')).rejects.toThrow(
      /Failed to fetch/
    );
  });
});
