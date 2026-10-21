/**
 * multipartResumeStorage tests — Phase 260.3.F.1.
 *
 * Pure-function tests for the resumable-upload checkpoint persistence
 * helper. No HTTP, no React, no DOM beyond ``localStorage`` (jsdom-
 * provided in vitest's default test environment).
 *
 * Engineering invariants under test:
 *   - Identity: a fingerprint is deterministic per (userId, fileName, size,
 *     lastModified) so reloading with the same File object reaches the
 *     same checkpoint, while a different file (size, name, mtime) does
 *     NOT match.
 *   - Determinism: two checkpoints saved in any order can be enumerated
 *     by ``listResumableUploads`` in deterministic order (newest first).
 *   - TTL: a checkpoint older than ``RESUME_CHECKPOINT_TTL_MS`` is treated
 *     as stale (load returns null; pruneStaleCheckpoints purges it).
 *   - Robustness: corrupted JSON or schema-shape drift is recovered
 *     non-fatally (load returns null; storage continues to work).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  RESUME_CHECKPOINT_TTL_MS,
  RESUME_STORAGE_KEY,
  buildUploadFingerprint,
  clearUploadCheckpoint,
  listResumableUploads,
  loadUploadCheckpoint,
  pruneStaleCheckpoints,
  saveUploadCheckpoint,
  type UploadCheckpoint,
} from './multipartResumeStorage';

const FIXED_NOW = Date.parse('2026-05-05T10:00:00Z');

function makeCheckpoint(overrides: Partial<UploadCheckpoint> = {}): UploadCheckpoint {
  return {
    fingerprint: 'fp-1',
    fileId: 'file-1',
    uploadId: 'mpu-1',
    fileName: 'big.csv',
    contentType: 'text/csv',
    totalSize: 200 * 1024 * 1024,
    chunkSize: 50 * 1024 * 1024,
    chunkCount: 4,
    completedParts: [],
    startedAt: FIXED_NOW,
    updatedAt: FIXED_NOW,
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

describe('buildUploadFingerprint', () => {
  it('returns the same fingerprint for identical inputs', () => {
    const a = buildUploadFingerprint({
      userId: 'u-1',
      fileName: 'data.csv',
      size: 12345,
      lastModified: 9_000,
    });
    const b = buildUploadFingerprint({
      userId: 'u-1',
      fileName: 'data.csv',
      size: 12345,
      lastModified: 9_000,
    });
    expect(a).toBe(b);
    expect(typeof a).toBe('string');
    expect(a.length).toBeGreaterThan(0);
  });

  it('differs when any input dimension differs', () => {
    const base = {
      userId: 'u-1',
      fileName: 'data.csv',
      size: 12345,
      lastModified: 9_000,
    } as const;
    const f = buildUploadFingerprint(base);
    expect(buildUploadFingerprint({ ...base, userId: 'u-2' })).not.toBe(f);
    expect(buildUploadFingerprint({ ...base, fileName: 'other.csv' })).not.toBe(f);
    expect(buildUploadFingerprint({ ...base, size: 12346 })).not.toBe(f);
    expect(buildUploadFingerprint({ ...base, lastModified: 9_001 })).not.toBe(f);
  });
});

describe('saveUploadCheckpoint + loadUploadCheckpoint', () => {
  it('round-trips a fresh checkpoint', () => {
    const checkpoint = makeCheckpoint({ fingerprint: 'fp-A' });
    saveUploadCheckpoint(checkpoint);
    const loaded = loadUploadCheckpoint('fp-A');
    expect(loaded).toEqual(checkpoint);
  });

  it('overwrites an existing checkpoint with the same fingerprint and bumps updatedAt', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-A', completedParts: [] }));
    const updated = makeCheckpoint({
      fingerprint: 'fp-A',
      completedParts: [{ partNumber: 1, etag: '"abc"' }],
      updatedAt: FIXED_NOW + 1000,
    });
    saveUploadCheckpoint(updated);
    const loaded = loadUploadCheckpoint('fp-A');
    expect(loaded?.completedParts).toEqual([{ partNumber: 1, etag: '"abc"' }]);
    expect(loaded?.updatedAt).toBe(FIXED_NOW + 1000);
  });

  it('returns null when no checkpoint exists for the fingerprint', () => {
    expect(loadUploadCheckpoint('not-found')).toBeNull();
  });

  it('returns null and DOES NOT throw on corrupted JSON', () => {
    localStorage.setItem(RESUME_STORAGE_KEY, '{{not-json');
    expect(loadUploadCheckpoint('fp-A')).toBeNull();
    expect(listResumableUploads()).toEqual([]);
  });

  it('returns null on schema-shape drift (missing required field)', () => {
    localStorage.setItem(
      RESUME_STORAGE_KEY,
      JSON.stringify({ 'fp-A': { fingerprint: 'fp-A' /* missing required fields */ } })
    );
    expect(loadUploadCheckpoint('fp-A')).toBeNull();
  });
});

describe('TTL', () => {
  it('treats checkpoints older than RESUME_CHECKPOINT_TTL_MS as stale (load returns null)', () => {
    const stale = makeCheckpoint({
      fingerprint: 'fp-OLD',
      updatedAt: FIXED_NOW - RESUME_CHECKPOINT_TTL_MS - 1,
    });
    saveUploadCheckpoint(stale);
    expect(loadUploadCheckpoint('fp-OLD')).toBeNull();
  });

  it('keeps checkpoints exactly at the TTL boundary (still fresh)', () => {
    const edge = makeCheckpoint({
      fingerprint: 'fp-EDGE',
      updatedAt: FIXED_NOW - RESUME_CHECKPOINT_TTL_MS,
    });
    saveUploadCheckpoint(edge);
    expect(loadUploadCheckpoint('fp-EDGE')).not.toBeNull();
  });

  it('pruneStaleCheckpoints removes only the stale entries', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-FRESH', updatedAt: FIXED_NOW }));
    saveUploadCheckpoint(
      makeCheckpoint({
        fingerprint: 'fp-STALE',
        updatedAt: FIXED_NOW - RESUME_CHECKPOINT_TTL_MS - 60_000,
      })
    );
    const prunedCount = pruneStaleCheckpoints();
    expect(prunedCount).toBe(1);
    expect(loadUploadCheckpoint('fp-FRESH')).not.toBeNull();
    expect(loadUploadCheckpoint('fp-STALE')).toBeNull();
  });
});

describe('listResumableUploads', () => {
  it('returns checkpoints sorted by updatedAt descending (newest first)', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-A', updatedAt: FIXED_NOW - 5000 }));
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-B', updatedAt: FIXED_NOW - 100 }));
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-C', updatedAt: FIXED_NOW - 2000 }));
    const list = listResumableUploads();
    expect(list.map((c) => c.fingerprint)).toEqual(['fp-B', 'fp-C', 'fp-A']);
  });

  it('omits stale checkpoints from the listing', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-FRESH', updatedAt: FIXED_NOW }));
    saveUploadCheckpoint(
      makeCheckpoint({
        fingerprint: 'fp-STALE',
        updatedAt: FIXED_NOW - RESUME_CHECKPOINT_TTL_MS - 1,
      })
    );
    const list = listResumableUploads();
    expect(list.map((c) => c.fingerprint)).toEqual(['fp-FRESH']);
  });

  it('returns an empty array when no checkpoints exist', () => {
    expect(listResumableUploads()).toEqual([]);
  });
});

describe('clearUploadCheckpoint', () => {
  it('removes the keyed checkpoint without disturbing siblings', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-A' }));
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-B' }));
    clearUploadCheckpoint('fp-A');
    expect(loadUploadCheckpoint('fp-A')).toBeNull();
    expect(loadUploadCheckpoint('fp-B')).not.toBeNull();
  });

  it('is a safe no-op for unknown fingerprints', () => {
    expect(() => clearUploadCheckpoint('does-not-exist')).not.toThrow();
  });

  it('removes the storage key entirely when the last checkpoint is cleared', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-LAST' }));
    clearUploadCheckpoint('fp-LAST');
    expect(localStorage.getItem(RESUME_STORAGE_KEY)).toBeNull();
  });
});

describe('storage hardening', () => {
  it('survives a localStorage write quota exception non-fatally', () => {
    const setItemSpy = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementationOnce(() => {
        throw new Error('QuotaExceededError');
      });
    expect(() => saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-Q' }))).not.toThrow();
    setItemSpy.mockRestore();
  });
});
