/**
 * Phase 260.3.F.2 — UI hook surfacing the list of resumable uploads
 * and a ``discard`` action.
 *
 * State source-of-truth is :func:`listResumableUploads`, which reads
 * the durable localStorage map. We refresh on:
 *   - mount (so the resume-prompt appears on a fresh page load),
 *   - explicit ``refresh()`` calls (after a successful resume / start),
 *   - cross-tab ``storage`` events (so a checkpoint added in another
 *     tab appears here without a manual reload).
 */

import { useCallback, useEffect, useState } from 'react';

import {
  RESUME_STORAGE_KEY,
  clearUploadCheckpoint,
  listResumableUploads,
  type UploadCheckpoint,
} from '../utils/multipartResumeStorage';

export interface UseResumableUploadsResult {
  checkpoints: UploadCheckpoint[];
  discard: (fingerprint: string) => void;
  refresh: () => void;
}

export function useResumableUploads(): UseResumableUploadsResult {
  const [checkpoints, setCheckpoints] = useState<UploadCheckpoint[]>(() =>
    listResumableUploads()
  );

  const refresh = useCallback(() => {
    setCheckpoints(listResumableUploads());
  }, []);

  const discard = useCallback(
    (fingerprint: string) => {
      clearUploadCheckpoint(fingerprint);
      setCheckpoints(listResumableUploads());
    },
    []
  );

  useEffect(() => {
    const handler = (event: StorageEvent) => {
      if (event.key === null || event.key === RESUME_STORAGE_KEY) {
        refresh();
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, [refresh]);

  return { checkpoints, discard, refresh };
}
