/**
 * useResumableUploads tests — Phase 260.3.F.2 + 260.3.F.UX.
 *
 * The hook exposes the list of resumable uploads from
 * ``listResumableUploads`` and provides a ``discard`` action that
 * clears the localStorage checkpoint. Real localStorage backs the
 * helper; no mocks of the storage layer.
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  RESUME_STORAGE_KEY,
  saveUploadCheckpoint,
  type UploadCheckpoint,
} from '../utils/multipartResumeStorage';
import { useResumableUploads } from './useResumableUploads';

const FIXED_NOW = Date.parse('2026-05-05T10:00:00Z');

function makeCheckpoint(overrides: Partial<UploadCheckpoint> = {}): UploadCheckpoint {
  return {
    fingerprint: 'fp-A',
    fileId: 'file-A',
    uploadId: 'mpu-A',
    fileName: 'big.csv',
    contentType: 'text/csv',
    totalSize: 200 * 1024 * 1024,
    chunkSize: 50 * 1024 * 1024,
    chunkCount: 4,
    completedParts: [{ partNumber: 1, etag: '"abc"' }],
    startedAt: FIXED_NOW - 5000,
    updatedAt: FIXED_NOW - 5000,
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
});

describe('useResumableUploads', () => {
  it('returns an empty list when no checkpoints exist', () => {
    const { result } = renderHook(() => useResumableUploads());
    expect(result.current.checkpoints).toEqual([]);
  });

  it('returns checkpoints sorted by updatedAt desc on initial render', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-1', updatedAt: FIXED_NOW - 5_000 }));
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-2', updatedAt: FIXED_NOW - 100 }));
    const { result } = renderHook(() => useResumableUploads());
    expect(result.current.checkpoints.map((c) => c.fingerprint)).toEqual(['fp-2', 'fp-1']);
  });

  it('discard removes the keyed checkpoint and refreshes the list', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-1' }));
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-2', updatedAt: FIXED_NOW - 100 }));
    const { result } = renderHook(() => useResumableUploads());
    act(() => {
      result.current.discard('fp-1');
    });
    expect(result.current.checkpoints.map((c) => c.fingerprint)).toEqual(['fp-2']);
  });

  it('refresh re-reads the list (after a checkpoint is added in another tab)', () => {
    const { result } = renderHook(() => useResumableUploads());
    expect(result.current.checkpoints).toEqual([]);
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-LATE' }));
    act(() => {
      result.current.refresh();
    });
    expect(result.current.checkpoints.map((c) => c.fingerprint)).toEqual(['fp-LATE']);
  });

  it('reacts to ``storage`` events from other tabs', () => {
    const { result } = renderHook(() => useResumableUploads());
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-OTHER-TAB' }));
    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: RESUME_STORAGE_KEY,
          newValue: localStorage.getItem(RESUME_STORAGE_KEY),
        })
      );
    });
    expect(result.current.checkpoints.map((c) => c.fingerprint)).toEqual(['fp-OTHER-TAB']);
  });
});
