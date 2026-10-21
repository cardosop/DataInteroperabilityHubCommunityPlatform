/**
 * MultipartUploader tests — Phase 260.3.F.
 *
 * Behavioral tests for the orchestrator that drives the actual S3
 * multipart upload from the browser, persisting a localStorage
 * checkpoint after every successful part PUT and supporting
 * resume-from-checkpoint after a network failure or tab reload.
 *
 * Boundaries that ARE mocked (justified): the HTTP/XHR boundary
 * — ``apiClient.getClient()`` for backend calls, the S3 PUT
 * (replaced with a deterministic fake transport injected via
 * constructor option) for the chunk uploads. Everything ELSE is
 * real: the ``multipartResumeStorage`` localStorage helper, the
 * ``Blob.slice`` chunking, the part-number / ETag bookkeeping, the
 * reconciliation algorithm.
 *
 * Engineering invariants under test:
 *   - Single-PUT path: small files take the simple presigned URL flow
 *     and never touch the multipart state machine.
 *   - Multipart path: each chunk is sliced from the source Blob,
 *     PUT to the per-chunk presigned URL captured from
 *     ``initChunkUpload``, and the returned ETag header is captured
 *     into the in-memory + persisted parts list.
 *   - Checkpoint cadence: after every successful PUT the localStorage
 *     checkpoint reflects the exact set of completed parts (ordered
 *     by partNumber asc).
 *   - Failure isolation: when one PUT rejects, NO further PUTs fire,
 *     and the checkpoint reflects only the parts that actually
 *     succeeded.
 *   - Resume-fast-path: when ``resumeFrom`` is supplied, ``init`` is
 *     NOT called again — the existing fileId / uploadId is reused
 *     and only the missing parts are uploaded.
 *   - S3-truth reconciliation: when the backend ``listParts`` reports
 *     parts that the local checkpoint missed, the reconciler keeps
 *     S3's view as authoritative (uploads only the parts S3 doesn't
 *     have).
 *   - Completion path: on ``complete`` success, the checkpoint is
 *     cleared so a finished upload never appears in the resume list.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import {
  RESUME_STORAGE_KEY,
  loadUploadCheckpoint,
  type UploadCheckpoint,
} from './multipartResumeStorage';
import {
  MultipartUploader,
  type ChunkPutFn,
} from './multipartUploader';

const FIXED_NOW = Date.parse('2026-05-05T10:00:00Z');

function makeBlob(size: number, byte = 0x41): Blob {
  return new Blob([new Uint8Array(size).fill(byte)], { type: 'text/csv' });
}

function makeFakeFile(size: number, name = 'big.csv', lastModified = 1234): File {
  const blob = makeBlob(size);
  // jsdom File constructor accepts BlobParts + name + options.
  return new File([blob], name, { type: 'text/csv', lastModified });
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  vi.useFakeTimers();
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
});

describe('MultipartUploader — single-PUT path (file ≤ multipart threshold)', () => {
  it('uploads the file in one PUT and never touches the multipart state machine', async () => {
    const file = makeFakeFile(1024);
    const initResponse = {
      file_id: 'file-1',
      upload_url: 'https://s3.example.com/presigned-simple-put',
      requires_multipart: false,
    };
    const completedFile = { id: 'file-1', name: 'big.csv' };
    const httpMock = vi.mocked(apiClient.getClient());
    vi.mocked(httpMock.post).mockImplementation(((url: string) => {
      if (url.endsWith('files/init/')) return Promise.resolve({ data: initResponse }) as never;
      if (url.endsWith('/complete/'))
        return Promise.resolve({ data: completedFile }) as never;
      throw new Error(`unexpected POST ${url}`);
    }) as never);

    const chunkPuts: Array<{ url: string; size: number }> = [];
    const fakePut: ChunkPutFn = async (url, blob) => {
      chunkPuts.push({ url, size: blob.size });
      return { etag: '"single-etag"' };
    };

    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });
    const result = await uploader.upload(file);

    expect(result.id).toBe('file-1');
    expect(chunkPuts).toEqual([
      { url: 'https://s3.example.com/presigned-simple-put', size: 1024 },
    ]);
    // Single-PUT path NEVER persists a checkpoint.
    expect(localStorage.getItem(RESUME_STORAGE_KEY)).toBeNull();
  });
});

describe('MultipartUploader — multipart path', () => {
  function setupMultipartHttpMocks(opts: {
    initFileId?: string;
    initUploadId?: string;
    chunkSize?: number;
    chunkCount?: number;
    completedFile?: object;
  }) {
    const httpMock = vi.mocked(apiClient.getClient());
    const fileId = opts.initFileId ?? 'file-mp-1';
    const uploadId = opts.initUploadId ?? 'mpu-abc';
    const chunkSize = opts.chunkSize ?? 5 * 1024 * 1024;
    const chunkCount = opts.chunkCount ?? 3;
    const completedFile = opts.completedFile ?? { id: fileId, name: 'big.csv' };

    vi.mocked(httpMock.post).mockImplementation(((url: string, body?: unknown) => {
      if (url.endsWith('files/init/')) {
        return Promise.resolve({
          data: {
            file_id: fileId,
            upload_url: `https://s3.example.com/${uploadId}/part-1`,
            upload_id: uploadId,
            chunk_size: chunkSize,
            chunk_count: chunkCount,
            requires_multipart: true,
          },
        }) as never;
      }
      const partInitMatch = url.match(/(?:^|\/)files\/[^/]+\/chunks\/init\/$/);
      if (partInitMatch) {
        const payload = body as { chunk_number: number };
        return Promise.resolve({
          data: {
            upload_url: `https://s3.example.com/${uploadId}/part-${payload.chunk_number}`,
            expires_in: 3600,
          },
        }) as never;
      }
      if (url.endsWith('/complete/')) {
        return Promise.resolve({ data: completedFile }) as never;
      }
      throw new Error(`unexpected POST ${url}`);
    }) as never);

    vi.mocked(httpMock.get).mockImplementation(((_url: string) => {
      throw new Error(`unexpected GET ${_url}`);
    }) as never);

    return { fileId, uploadId, chunkSize, chunkCount, completedFile };
  }

  it('iterates every chunk, captures ETags, and completes', async () => {
    const ctx = setupMultipartHttpMocks({ chunkCount: 3, chunkSize: 5 });
    const file = makeFakeFile(15);

    const chunkPuts: Array<{ url: string; size: number }> = [];
    const fakePut: ChunkPutFn = async (url, blob) => {
      chunkPuts.push({ url, size: blob.size });
      const partNumber = Number(url.split('/part-')[1]);
      return { etag: `"etag-${partNumber}"` };
    };

    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });
    const result = await uploader.upload(file);

    expect(result.id).toBe(ctx.fileId);
    expect(chunkPuts.length).toBe(3);
    expect(chunkPuts.map((c) => c.size)).toEqual([5, 5, 5]);
    // Final complete must have been called with the in-order parts list.
    const httpMock = vi.mocked(apiClient.getClient());
    const completeCall = vi
      .mocked(httpMock.post)
      .mock.calls.find((call) => String(call[0]).endsWith('/complete/'));
    expect(completeCall?.[1]).toMatchObject({
      parts: [
        { PartNumber: 1, ETag: '"etag-1"' },
        { PartNumber: 2, ETag: '"etag-2"' },
        { PartNumber: 3, ETag: '"etag-3"' },
      ],
    });
  });

  it('persists a checkpoint after every successful chunk PUT', async () => {
    setupMultipartHttpMocks({ chunkCount: 3, chunkSize: 5 });
    const file = makeFakeFile(15);

    const checkpointSnapshots: number[] = [];
    const fakePut: ChunkPutFn = async (url) => {
      const partNumber = Number(url.split('/part-')[1]);
      // After this PUT resolves, the uploader must persist N parts.
      // We capture in the assertion below.
      void checkpointSnapshots;
      return { etag: `"etag-${partNumber}"` };
    };

    const uploader = new MultipartUploader({
      chunkPut: fakePut,
      userId: 'u-1',
      onCheckpoint: (cp) => {
        checkpointSnapshots.push(cp.completedParts.length);
      },
    });
    await uploader.upload(file);

    // Baseline checkpoint after init (0 parts) + one per successful PUT.
    // The baseline is GAP-A defence — even a part-1 failure leaves a
    // resumable upload-id behind instead of stranding the S3 multipart.
    expect(checkpointSnapshots).toEqual([0, 1, 2, 3]);
    // After complete(), checkpoint MUST be cleared.
    expect(localStorage.getItem(RESUME_STORAGE_KEY)).toBeNull();
  });

  it('persists a baseline checkpoint immediately after init, before any chunk PUT', async () => {
    setupMultipartHttpMocks({ chunkCount: 3, chunkSize: 5 });
    const file = makeFakeFile(15);

    let baselineSeenBeforePuts = false;
    const fakePut: ChunkPutFn = async (url) => {
      // First time we get into chunkPut, the baseline checkpoint must
      // already be on disk (so a network kill HERE is recoverable).
      const map = JSON.parse(localStorage.getItem(RESUME_STORAGE_KEY) || '{}');
      const fingerprints = Object.keys(map);
      if (fingerprints.length > 0 && map[fingerprints[0]].completedParts.length === 0) {
        baselineSeenBeforePuts = true;
      }
      const partNumber = Number(url.split('/part-')[1]);
      return { etag: `"baseline-${partNumber}"` };
    };
    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });
    await uploader.upload(file);
    expect(baselineSeenBeforePuts).toBe(true);
  });

  it('checkpoint includes all required fields and the per-part ETag', async () => {
    setupMultipartHttpMocks({ chunkCount: 2, chunkSize: 5 });
    const file = makeFakeFile(10);

    let lastCheckpoint: UploadCheckpoint | null = null;
    const fakePut: ChunkPutFn = async (url) => {
      const partNumber = Number(url.split('/part-')[1]);
      return { etag: `"etag-${partNumber}"` };
    };
    const uploader = new MultipartUploader({
      chunkPut: fakePut,
      userId: 'u-1',
      onCheckpoint: (cp) => {
        lastCheckpoint = cp;
      },
    });
    await uploader.upload(file);
    expect(lastCheckpoint).not.toBeNull();
    const cp = lastCheckpoint as unknown as UploadCheckpoint;
    expect(cp.fileId).toBe('file-mp-1');
    expect(cp.uploadId).toBe('mpu-abc');
    expect(cp.completedParts).toEqual([
      { partNumber: 1, etag: '"etag-1"' },
      { partNumber: 2, etag: '"etag-2"' },
    ]);
    expect(cp.totalSize).toBe(10);
    expect(cp.chunkSize).toBe(5);
    expect(cp.chunkCount).toBe(2);
  });

  it('GAP-A: a failure on the very first chunk leaves a baseline checkpoint behind', async () => {
    setupMultipartHttpMocks({ chunkCount: 4, chunkSize: 5 });
    const file = makeFakeFile(20);
    const fakePut: ChunkPutFn = async () => {
      throw new Error('network down before part 1 finished');
    };
    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });

    await expect(uploader.upload(file)).rejects.toThrow(/network down/);

    // Even though zero parts were durable, the baseline checkpoint is
    // on disk — the user can refresh and resume against the same
    // upload_id instead of stranding the S3 multipart as an orphan.
    const fingerprint = uploader.computeFingerprint(file);
    const persisted = loadUploadCheckpoint(fingerprint);
    expect(persisted).not.toBeNull();
    expect(persisted?.uploadId).toBe('mpu-abc');
    expect(persisted?.completedParts).toEqual([]);
  });

  it('halts on chunk PUT failure with the partial checkpoint preserved', async () => {
    setupMultipartHttpMocks({ chunkCount: 4, chunkSize: 5 });
    const file = makeFakeFile(20);

    let putAttempts = 0;
    const fakePut: ChunkPutFn = async (url) => {
      putAttempts += 1;
      const partNumber = Number(url.split('/part-')[1]);
      if (partNumber === 3) {
        throw new Error('network kill');
      }
      return { etag: `"etag-${partNumber}"` };
    };
    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });

    await expect(uploader.upload(file)).rejects.toThrow(/network kill/);

    // Exactly 3 PUTs attempted (1, 2, 3) — no part-4 try after the failure.
    expect(putAttempts).toBe(3);

    // Checkpoint preserved with parts 1 + 2 only.
    const fingerprint = uploader.computeFingerprint(file);
    const persisted = loadUploadCheckpoint(fingerprint);
    expect(persisted?.completedParts).toEqual([
      { partNumber: 1, etag: '"etag-1"' },
      { partNumber: 2, etag: '"etag-2"' },
    ]);
  });
});

describe('MultipartUploader — resume', () => {
  it('skips init() when resuming and only PUTs the missing parts', async () => {
    const httpMock = vi.mocked(apiClient.getClient());
    const completedFile = { id: 'file-rsm-1', name: 'big.csv' };
    vi.mocked(httpMock.post).mockImplementation(((url: string, body?: unknown) => {
      if (url.endsWith('files/init/')) {
        throw new Error('init must NOT be called on the resume path');
      }
      const partInitMatch = url.match(/(?:^|\/)files\/[^/]+\/chunks\/init\/$/);
      if (partInitMatch) {
        const payload = body as { chunk_number: number };
        return Promise.resolve({
          data: {
            upload_url: `https://s3.example.com/resume/part-${payload.chunk_number}`,
            expires_in: 3600,
          },
        }) as never;
      }
      if (url.endsWith('/complete/')) {
        return Promise.resolve({ data: completedFile }) as never;
      }
      throw new Error(`unexpected POST ${url}`);
    }) as never);
    // Backend list-parts confirms parts 1 + 2 are durably in S3.
    vi.mocked(httpMock.get).mockImplementation(((url: string) => {
      if (url.match(/(?:^|\/)files\/[^/]+\/parts\/$/)) {
        return Promise.resolve({
          data: {
            upload_id: 'mpu-resume',
            parts: [
              { part_number: 1, etag: '"e1"', size: 5 },
              { part_number: 2, etag: '"e2"', size: 5 },
            ],
          },
        }) as never;
      }
      throw new Error(`unexpected GET ${url}`);
    }) as never);

    const file = makeFakeFile(15);
    const fakePut: ChunkPutFn = async (url) => {
      const partNumber = Number(url.split('/part-')[1]);
      return { etag: `"e${partNumber}"` };
    };
    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });
    const fingerprint = uploader.computeFingerprint(file);

    const result = await uploader.resume(file, {
      fingerprint,
      fileId: 'file-rsm-1',
      uploadId: 'mpu-resume',
      fileName: 'big.csv',
      contentType: 'text/csv',
      totalSize: 15,
      chunkSize: 5,
      chunkCount: 3,
      completedParts: [
        { partNumber: 1, etag: '"e1"' },
        { partNumber: 2, etag: '"e2"' },
      ],
      startedAt: FIXED_NOW - 5000,
      updatedAt: FIXED_NOW - 1000,
    });

    expect(result.id).toBe('file-rsm-1');
    // ONE chunk-init call (for part 3) and ONE PUT (for part 3).
    const partInitCalls = vi
      .mocked(httpMock.post)
      .mock.calls.filter((c) => /\/chunks\/init\/$/.test(String(c[0])));
    expect(partInitCalls).toHaveLength(1);
    expect(partInitCalls[0][1]).toMatchObject({ chunk_number: 3 });
  });

  it('lets S3 truth override stale local checkpoint when reconciling', async () => {
    const httpMock = vi.mocked(apiClient.getClient());
    vi.mocked(httpMock.post).mockImplementation(((url: string, body?: unknown) => {
      const partInitMatch = url.match(/(?:^|\/)files\/[^/]+\/chunks\/init\/$/);
      if (partInitMatch) {
        const payload = body as { chunk_number: number };
        return Promise.resolve({
          data: {
            upload_url: `https://s3.example.com/reconcile/part-${payload.chunk_number}`,
            expires_in: 3600,
          },
        }) as never;
      }
      if (url.endsWith('/complete/')) {
        return Promise.resolve({ data: { id: 'file-rec-1', name: 'big.csv' } }) as never;
      }
      throw new Error(`unexpected POST ${url}`);
    }) as never);
    // Local checkpoint thinks only part 1 is done. S3 actually has 1 + 2.
    // Reconciler MUST adopt S3's view.
    vi.mocked(httpMock.get).mockImplementation((() =>
      Promise.resolve({
        data: {
          upload_id: 'mpu-rec',
          parts: [
            { part_number: 1, etag: '"E1-server"', size: 5 },
            { part_number: 2, etag: '"E2-server"', size: 5 },
          ],
        },
      }) as never) as never);

    const file = makeFakeFile(15);
    const partsSeen: number[] = [];
    const fakePut: ChunkPutFn = async (url) => {
      const partNumber = Number(url.split('/part-')[1]);
      partsSeen.push(partNumber);
      return { etag: `"local-${partNumber}"` };
    };
    const uploader = new MultipartUploader({ chunkPut: fakePut, userId: 'u-1' });
    await uploader.resume(file, {
      fingerprint: uploader.computeFingerprint(file),
      fileId: 'file-rec-1',
      uploadId: 'mpu-rec',
      fileName: 'big.csv',
      contentType: 'text/csv',
      totalSize: 15,
      chunkSize: 5,
      chunkCount: 3,
      completedParts: [{ partNumber: 1, etag: '"local-stale"' }],
      startedAt: FIXED_NOW - 1000,
      updatedAt: FIXED_NOW - 100,
    });

    // ONLY part 3 was PUT; S3-truth said 1 + 2 were already there.
    expect(partsSeen).toEqual([3]);
    // Final complete used S3's authoritative ETags for 1 + 2.
    const completeCall = vi
      .mocked(httpMock.post)
      .mock.calls.find((c) => String(c[0]).endsWith('/complete/'));
    expect(completeCall?.[1]).toMatchObject({
      parts: [
        { PartNumber: 1, ETag: '"E1-server"' },
        { PartNumber: 2, ETag: '"E2-server"' },
        { PartNumber: 3, ETag: '"local-3"' },
      ],
    });
  });
});
