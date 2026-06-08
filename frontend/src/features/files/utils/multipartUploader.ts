/**
 * Phase 260.3.F — orchestrator for resumable S3 multipart uploads from
 * the browser.
 *
 * Responsibilities
 * ----------------
 * 1. **Drive the actual multipart loop** the backend has supported all
 *    along but the frontend used to flatten into a single PUT (see
 *    ``fileService.uploadFile`` history): on ``init`` returning
 *    ``requires_multipart=true``, slice the source ``Blob`` into
 *    ``chunk_count`` parts, request a presigned URL per chunk via
 *    ``POST /files/{id}/chunks/init/``, ``PUT`` the slice, capture the
 *    ETag header.
 * 2. **Persist a checkpoint after every successful PUT** via
 *    :func:`saveUploadCheckpoint` so a tab reload or network kill can
 *    resume from the last durable state.
 * 3. **Reconcile against S3 truth on resume** via
 *    ``GET /files/{id}/parts/`` — when local checkpoint and S3 disagree
 *    (a part was lost mid-PUT, or a different tab uploaded a part),
 *    the S3 view wins because S3 is the durable store.
 *
 * Boundaries
 * ----------
 * The ``chunkPut`` transport is injected so unit tests can drive a
 * deterministic fake (no real S3 / fetch / XHR), while production
 * wires the real :func:`xhrChunkPut` (browser ``XMLHttpRequest`` PUT
 * that captures the ``ETag`` response header). Everything else
 * (chunking, checkpointing, reconciliation) is real.
 */

import { apiClient } from '../../../shared/api/client';
import {
  buildUploadFingerprint,
  clearUploadCheckpoint,
  saveUploadCheckpoint,
  type UploadCheckpoint,
  type UploadPart,
} from './multipartResumeStorage';

const FILES_BASE_PATH = 'files';

export interface ChunkPutResult {
  /** S3 ``ETag`` response header (with surrounding quotes preserved). */
  etag: string;
}

/**
 * Transport function that PUTs ``blob`` to ``url`` and returns the
 * S3 ``ETag`` header. Injected for testability; production uses
 * :func:`xhrChunkPut`.
 */
export type ChunkPutFn = (
  url: string,
  blob: Blob,
  options?: { onProgress?: (loaded: number, total: number) => void }
) => Promise<ChunkPutResult>;

export interface UploadFileResult {
  id: string;
  [extra: string]: unknown;
}

interface InitResponse {
  file_id: string;
  upload_url: string;
  upload_id?: string;
  chunk_size?: number;
  chunk_count?: number;
  requires_multipart?: boolean;
  fields?: Record<string, string>;
}

interface ChunkInitResponse {
  upload_url: string;
  expires_in: number;
}

interface PartsResponse {
  upload_id: string;
  parts: Array<{ part_number: number; etag: string; size: number }>;
}

export interface MultipartUploaderOptions {
  /** Per-chunk PUT transport (DI hook for tests). */
  chunkPut: ChunkPutFn;
  /**
   * Currently authenticated user id, mixed into the fingerprint so
   * different users on the same browser don't see each other's
   * checkpoints.
   */
  userId: string;
  /** Optional progress + checkpoint observer hooks. */
  onProgress?: (progress: number) => void;
  onCheckpoint?: (checkpoint: UploadCheckpoint) => void;
}

export interface UploadOptions {
  /** Override the file name reported to the backend. */
  name?: string;
  /** Per-byte progress signal (cumulative across all chunks). */
  onProgress?: (progress: number) => void;
}

/**
 * Production XHR-based chunk PUT. Used by ``MultipartUploader`` when no
 * test injects a fake transport. Captures the ``ETag`` response header
 * and surfaces network / HTTP failures via rejected Promise.
 */
export const xhrChunkPut: ChunkPutFn = async (url, blob, options) =>
  new Promise<ChunkPutResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    if (options?.onProgress) {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          options.onProgress!(event.loaded, event.total);
        }
      });
    }
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const etag = xhr.getResponseHeader('ETag') || xhr.getResponseHeader('etag');
        if (!etag) {
          reject(new Error('S3 PUT succeeded but did not expose an ETag header'));
          return;
        }
        resolve({ etag });
      } else {
        reject(new Error(`S3 part PUT failed with status ${xhr.status}: ${xhr.responseText}`));
      }
    });
    xhr.addEventListener('error', () => reject(new Error('S3 part PUT network error')));
    xhr.addEventListener('abort', () => reject(new Error('S3 part PUT aborted')));
    xhr.addEventListener('timeout', () => reject(new Error('S3 part PUT timeout')));
    xhr.timeout = 120_000;
    xhr.open('PUT', url);
    xhr.setRequestHeader('Content-Type', blob.type || 'application/octet-stream');
    xhr.send(blob);
  });

/**
 * Compute a SHA-256 of a Blob via ``crypto.subtle.digest``. Matches the
 * existing :meth:`fileService.calculateFileHash` semantics so the
 * server-side checksum verification path is unchanged.
 */
async function calculateFileHash(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export class MultipartUploader {
  private readonly options: MultipartUploaderOptions;

  constructor(options: MultipartUploaderOptions) {
    this.options = options;
  }

  /**
   * Build the deterministic fingerprint used to key a checkpoint for
   * this (user, file) pair. Exposed so callers can ``loadUploadCheckpoint``
   * before deciding to resume.
   */
  computeFingerprint(file: File): string {
    return buildUploadFingerprint({
      userId: this.options.userId,
      fileName: file.name,
      size: file.size,
      lastModified: file.lastModified,
    });
  }

  /**
   * Run a fresh upload. If the backend says ``requires_multipart``, take
   * the multipart loop with checkpointing. Otherwise take the single-PUT
   * fast path (no checkpoint persisted — the upload either succeeds or
   * the user retries from zero).
   */
  async upload(file: File, options: UploadOptions = {}): Promise<UploadFileResult> {
    const fileName = options.name ?? file.name;
    const contentType = file.type || 'application/octet-stream';

    const initResponse = await this.callInit({
      name: fileName,
      contentType,
      size: file.size,
    });

    if (!initResponse.requires_multipart) {
      // Single-PUT path — preserves the historical fast path for small
      // files. No checkpoint, no reconciliation needed.
      await this.options.chunkPut(initResponse.upload_url, file, {
        onProgress: (loaded, total) => {
          options.onProgress?.((loaded / total) * 100);
          this.options.onProgress?.((loaded / total) * 100);
        },
      });
      const sha256 = await calculateFileHash(file);
      return await this.callComplete(initResponse.file_id, sha256, []);
    }

    // GAP-A fix (audit-pass 2026-05-05): persist a baseline checkpoint
    // BEFORE the first chunk PUT so a network failure during part 1
    // is still resumable (re-using the same multipart upload_id
    // instead of stranding it as an S3 orphan + starting over).
    const baselineNow = Date.now();
    const baseline: UploadCheckpoint = {
      fingerprint: this.computeFingerprint(file),
      fileId: initResponse.file_id,
      uploadId: initResponse.upload_id!,
      fileName,
      contentType,
      totalSize: file.size,
      chunkSize: initResponse.chunk_size!,
      chunkCount: initResponse.chunk_count!,
      completedParts: [],
      startedAt: baselineNow,
      updatedAt: baselineNow,
    };
    saveUploadCheckpoint(baseline);
    this.options.onCheckpoint?.(baseline);

    return this.runMultipartLoop({
      file,
      fileName,
      contentType,
      fileId: initResponse.file_id,
      uploadId: initResponse.upload_id!,
      chunkSize: initResponse.chunk_size!,
      chunkCount: initResponse.chunk_count!,
      seedParts: [],
      firstChunkPresignedUrl: initResponse.upload_url,
      options,
    });
  }

  /**
   * Resume from a previously persisted checkpoint. Re-uses the existing
   * fileId / uploadId; reconciles against S3-truth via
   * :meth:`fileService.listParts`; uploads only the missing chunks.
   */
  async resume(file: File, checkpoint: UploadCheckpoint, options: UploadOptions = {}): Promise<UploadFileResult> {
    if (this.computeFingerprint(file) !== checkpoint.fingerprint) {
      throw new Error(
        'resume fingerprint mismatch — refusing to resume with a different file'
      );
    }
    if (file.size !== checkpoint.totalSize) {
      throw new Error('resume file size mismatch');
    }

    // Reconcile with S3 — server is authoritative.
    const reconciled = await this.reconcileWithServer(checkpoint);

    return this.runMultipartLoop({
      file,
      fileName: checkpoint.fileName,
      contentType: checkpoint.contentType,
      fileId: checkpoint.fileId,
      uploadId: checkpoint.uploadId,
      chunkSize: checkpoint.chunkSize,
      chunkCount: checkpoint.chunkCount,
      seedParts: reconciled,
      // Resume path: presigned URL for the next part is requested
      // explicitly via /chunks/init/ (we don't have a saved init URL).
      firstChunkPresignedUrl: null,
      options,
    });
  }

  // ------------------------------------------------------------------ //
  // Internals                                                          //
  // ------------------------------------------------------------------ //

  private async runMultipartLoop(args: {
    file: File;
    fileName: string;
    contentType: string;
    fileId: string;
    uploadId: string;
    chunkSize: number;
    chunkCount: number;
    seedParts: UploadPart[];
    firstChunkPresignedUrl: string | null;
    options: UploadOptions;
  }): Promise<UploadFileResult> {
    const {
      file,
      fileName,
      contentType,
      fileId,
      uploadId,
      chunkSize,
      chunkCount,
      seedParts,
      firstChunkPresignedUrl,
      options,
    } = args;

    const completed: UploadPart[] = [...seedParts].sort(
      (a, b) => a.partNumber - b.partNumber
    );
    const fingerprint = this.computeFingerprint(file);

    const persist = (now: number): UploadCheckpoint => {
      const checkpoint: UploadCheckpoint = {
        fingerprint,
        fileId,
        uploadId,
        fileName,
        contentType,
        totalSize: file.size,
        chunkSize,
        chunkCount,
        completedParts: [...completed].sort((a, b) => a.partNumber - b.partNumber),
        startedAt: now,
        updatedAt: now,
      };
      saveUploadCheckpoint(checkpoint);
      this.options.onCheckpoint?.(checkpoint);
      return checkpoint;
    };

    const completedSet = new Set(completed.map((p) => p.partNumber));
    let bytesUploaded = completed.length * chunkSize; // approx

    for (let partNumber = 1; partNumber <= chunkCount; partNumber += 1) {
      if (completedSet.has(partNumber)) continue;

      const start = (partNumber - 1) * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const chunk = file.slice(start, end, contentType);

      // Resume re-uses /chunks/init/ for every part. The fresh-upload
      // fast path can use the bundled first-chunk presigned URL the
      // backend returned from /init (one less round trip on the
      // happy path).
      let presignedUrl: string;
      if (partNumber === 1 && firstChunkPresignedUrl) {
        presignedUrl = firstChunkPresignedUrl;
      } else {
        const chunkInit = await this.callChunkInit(fileId, partNumber, chunk.size);
        presignedUrl = chunkInit.upload_url;
      }

      const result = await this.options.chunkPut(presignedUrl, chunk, {
        onProgress: (loaded) => {
          const totalAcc = bytesUploaded + loaded;
          const pct = (totalAcc / file.size) * 100;
          options.onProgress?.(pct);
          this.options.onProgress?.(pct);
        },
      });

      completed.push({ partNumber, etag: result.etag });
      completedSet.add(partNumber);
      bytesUploaded += chunk.size;
      persist(Date.now());
    }

    const sha256 = await calculateFileHash(file);
    const completeResult = await this.callComplete(
      fileId,
      sha256,
      completed
        .slice()
        .sort((a, b) => a.partNumber - b.partNumber)
        .map((p) => ({ PartNumber: p.partNumber, ETag: p.etag }))
    );
    clearUploadCheckpoint(fingerprint);
    return completeResult;
  }

  private async reconcileWithServer(checkpoint: UploadCheckpoint): Promise<UploadPart[]> {
    let response: PartsResponse;
    try {
      const httpResponse = await apiClient
        .getClient()
        .get<PartsResponse>(`${FILES_BASE_PATH}/${checkpoint.fileId}/parts/`);
      response = httpResponse.data;
    } catch (error) {
      // 409 means the multipart no longer exists — clear and rethrow so
      // caller surfaces "upload already completed; please retry".
      const httpError = error as { response?: { status?: number } };
      if (httpError.response?.status === 409) {
        clearUploadCheckpoint(checkpoint.fingerprint);
      }
      throw error;
    }

    if (response.upload_id !== checkpoint.uploadId) {
      // Server's notion of the upload differs from ours — the multipart
      // was likely re-initialised. Refuse to resume; caller clears the
      // checkpoint.
      clearUploadCheckpoint(checkpoint.fingerprint);
      throw new Error('multipart upload_id drift — checkpoint is stale');
    }

    return response.parts
      .map((p) => ({ partNumber: p.part_number, etag: p.etag }))
      .sort((a, b) => a.partNumber - b.partNumber);
  }

  private async callInit(payload: {
    name: string;
    contentType: string;
    size: number;
  }): Promise<InitResponse> {
    const response = await apiClient
      .getClient()
      .post<InitResponse>(`${FILES_BASE_PATH}/init/`, {
        name: payload.name,
        content_type: payload.contentType,
        size: payload.size,
        upload_method: 'browser',
      });
    return response.data;
  }

  private async callChunkInit(
    fileId: string,
    chunkNumber: number,
    chunkSize: number
  ): Promise<ChunkInitResponse> {
    const response = await apiClient
      .getClient()
      .post<ChunkInitResponse>(`${FILES_BASE_PATH}/${fileId}/chunks/init/`, {
        chunk_number: chunkNumber,
        chunk_size: chunkSize,
      });
    return response.data;
  }

  private async callComplete(
    fileId: string,
    contentSha256: string,
    parts: Array<{ PartNumber: number; ETag: string }>
  ): Promise<UploadFileResult> {
    const body: Record<string, unknown> = { content_sha256: contentSha256 };
    if (parts.length > 0) body.parts = parts;
    const response = await apiClient
      .getClient()
      .post<UploadFileResult>(`${FILES_BASE_PATH}/${fileId}/complete/`, body);
    return response.data;
  }
}
