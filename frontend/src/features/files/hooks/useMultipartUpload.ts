/**
 * Phase 260.3.F — orchestrator hook that wires :class:`MultipartUploader`
 * to the React Query upload mutation surface.
 *
 * Two action surfaces:
 *   - ``upload(file, options)`` — fresh upload; promotes to multipart
 *     automatically when the backend says ``requires_multipart``.
 *   - ``resume(file, checkpoint, options)`` — resume from a persisted
 *     checkpoint after a network failure / tab reload. The caller is
 *     responsible for fingerprint-matching: if the user picks a
 *     different file, ``resume`` will reject with a clear error.
 *
 * Both paths invalidate the ``files`` React Query cache on success so
 * the file list refreshes without a manual reload.
 */

import { useCallback, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { useAuthStore } from '../../auth/store/authStore';
import {
  MultipartUploader,
  xhrChunkPut,
  type UploadFileResult,
  type UploadOptions,
} from '../utils/multipartUploader';
import { type UploadCheckpoint } from '../utils/multipartResumeStorage';

interface UseMultipartUploadResult {
  upload: (file: File, options?: UploadOptions) => Promise<UploadFileResult>;
  resume: (
    file: File,
    checkpoint: UploadCheckpoint,
    options?: UploadOptions
  ) => Promise<UploadFileResult>;
  computeFingerprint: (file: File) => string | null;
  isPending: boolean;
  error: unknown;
  reset: () => void;
}

export function useMultipartUpload(): UseMultipartUploadResult {
  const userId = useAuthStore((s) => s.user?.id);
  const queryClient = useQueryClient();
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const uploader = useMemo(() => {
    if (!userId) return null;
    return new MultipartUploader({ chunkPut: xhrChunkPut, userId });
  }, [userId]);

  const upload = useCallback(
    async (file: File, options?: UploadOptions) => {
      if (!uploader) throw new Error('Cannot upload without an authenticated user');
      setIsPending(true);
      setError(null);
      try {
        const result = await uploader.upload(file, options);
        queryClient.invalidateQueries({ queryKey: ['files'] });
        return result;
      } catch (e) {
        setError(e);
        throw e;
      } finally {
        setIsPending(false);
      }
    },
    [uploader, queryClient]
  );

  const resume = useCallback(
    async (file: File, checkpoint: UploadCheckpoint, options?: UploadOptions) => {
      if (!uploader) throw new Error('Cannot resume without an authenticated user');
      setIsPending(true);
      setError(null);
      try {
        const result = await uploader.resume(file, checkpoint, options);
        queryClient.invalidateQueries({ queryKey: ['files'] });
        return result;
      } catch (e) {
        setError(e);
        throw e;
      } finally {
        setIsPending(false);
      }
    },
    [uploader, queryClient]
  );

  const computeFingerprint = useCallback(
    (file: File) => (uploader ? uploader.computeFingerprint(file) : null),
    [uploader]
  );

  const reset = useCallback(() => {
    setError(null);
    setIsPending(false);
  }, []);

  return { upload, resume, computeFingerprint, isPending, error, reset };
}
