/**
 * Phase 260.3.F.1 — durable client-side checkpoint store for resumable
 * multipart uploads.
 *
 * On each successful S3 part PUT, ``MultipartUploader`` calls
 * :func:`saveUploadCheckpoint` so a tab reload / network blip / browser
 * crash can resume from the last persisted state instead of restarting
 * the upload from chunk 1.
 *
 * Security / soundness invariants
 * --------------------------------
 * - **Identity is fingerprinted, not file-id-only.** A checkpoint is
 *   keyed by a deterministic fingerprint of (userId, fileName, size,
 *   lastModified) — *not* the backend ``fileId`` alone. That means a
 *   user who uploaded ``data.csv`` and then picks a different file with
 *   the same name CANNOT accidentally resume against the wrong file_id
 *   on the backend, and a different user CANNOT resume against a
 *   checkpoint that wasn't theirs (every authenticated session reads /
 *   writes its own keyed slot).
 * - **TTL bounds the blast radius.** Stale checkpoints (>
 *   ``RESUME_CHECKPOINT_TTL_MS`` since last update — default 24 h) are
 *   ignored on load and pruned on demand so abandoned uploads don't
 *   accumulate on disk.
 * - **Storage failures are non-fatal.** ``localStorage.setItem`` can
 *   throw under quota / private-mode / permission errors; we swallow
 *   write exceptions and log a warning so the upload pipeline keeps
 *   working (worst case: no resume, full restart).
 * - **Schema-shape drift is recovered non-fatally.** On any
 *   JSON / shape error we treat the slot as empty so a corrupted
 *   storage entry can't break new uploads. The bad entry is rewritten
 *   on the next successful save.
 */

import { debugLogger } from '../../../shared/utils/debugLogger';

export const RESUME_STORAGE_KEY = 'meshant.upload.resume.v1';
export const RESUME_CHECKPOINT_TTL_MS = 24 * 60 * 60 * 1000; // 24 h

export interface UploadPart {
  partNumber: number;
  etag: string;
}

export interface UploadCheckpoint {
  /** Deterministic per-(user, fileName, size, lastModified). */
  fingerprint: string;
  fileId: string;
  uploadId: string;
  fileName: string;
  contentType: string;
  totalSize: number;
  chunkSize: number;
  chunkCount: number;
  /** Strictly-increasing ETag list captured after each S3 ``PutPart``. */
  completedParts: UploadPart[];
  /** Epoch ms when ``init`` returned the upload_id. */
  startedAt: number;
  /** Epoch ms updated on every save (drives TTL). */
  updatedAt: number;
}

interface FingerprintInput {
  userId: string;
  fileName: string;
  size: number;
  lastModified: number;
}

/**
 * Build a deterministic fingerprint string for a (userId, fileName,
 * size, lastModified) tuple. Used as the localStorage map key.
 *
 * Implementation note: a stringified-tuple hash works fine here —
 * we don't need cryptographic strength because the fingerprint never
 * leaves the browser and never authenticates anything; it only
 * disambiguates checkpoints.
 */
export function buildUploadFingerprint(input: FingerprintInput): string {
  const { userId, fileName, size, lastModified } = input;
  // Fixed-format separator-bounded join so different inputs cannot
  // collide via string concatenation ("ab" + "c" vs "a" + "bc").
  return [
    encodeURIComponent(userId),
    encodeURIComponent(fileName),
    String(size),
    String(lastModified),
  ].join('|');
}

interface CheckpointMap {
  [fingerprint: string]: UploadCheckpoint;
}

function readMap(): CheckpointMap {
  let raw: string | null;
  try {
    raw = localStorage.getItem(RESUME_STORAGE_KEY);
  } catch {
    return {};
  }
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed as CheckpointMap;
  } catch {
    return {};
  }
}

function writeMap(map: CheckpointMap): void {
  try {
    if (Object.keys(map).length === 0) {
      localStorage.removeItem(RESUME_STORAGE_KEY);
      return;
    }
    localStorage.setItem(RESUME_STORAGE_KEY, JSON.stringify(map));
  } catch (error) {
    // Quota exceeded / private-mode / extension-blocked storage —
    // upload still works, just without resume support.
    debugLogger.warn('multipart_persist_failed', { error: String(error) });
  }
}

const REQUIRED_FIELDS: ReadonlyArray<keyof UploadCheckpoint> = [
  'fingerprint',
  'fileId',
  'uploadId',
  'fileName',
  'contentType',
  'totalSize',
  'chunkSize',
  'chunkCount',
  'completedParts',
  'startedAt',
  'updatedAt',
];

function isValidCheckpoint(entry: unknown): entry is UploadCheckpoint {
  if (!entry || typeof entry !== 'object') return false;
  const e = entry as Record<string, unknown>;
  for (const k of REQUIRED_FIELDS) {
    if (!(k in e)) return false;
  }
  if (!Array.isArray(e.completedParts)) return false;
  return true;
}

function isFresh(checkpoint: UploadCheckpoint, now: number): boolean {
  return now - checkpoint.updatedAt <= RESUME_CHECKPOINT_TTL_MS;
}

export function saveUploadCheckpoint(checkpoint: UploadCheckpoint): void {
  const map = readMap();
  map[checkpoint.fingerprint] = {
    ...checkpoint,
    updatedAt: checkpoint.updatedAt ?? Date.now(),
  };
  writeMap(map);
}

export function loadUploadCheckpoint(fingerprint: string): UploadCheckpoint | null {
  const map = readMap();
  const entry = map[fingerprint];
  if (!entry || !isValidCheckpoint(entry)) return null;
  if (!isFresh(entry, Date.now())) return null;
  return entry;
}

export function clearUploadCheckpoint(fingerprint: string): void {
  const map = readMap();
  if (!(fingerprint in map)) return;
  delete map[fingerprint];
  writeMap(map);
}

/**
 * Return all fresh checkpoints sorted by ``updatedAt`` desc. Used by
 * the upload UI to surface a "you have N pending uploads" prompt.
 */
export function listResumableUploads(): UploadCheckpoint[] {
  const map = readMap();
  const now = Date.now();
  const fresh: UploadCheckpoint[] = [];
  for (const key of Object.keys(map)) {
    const entry = map[key];
    if (isValidCheckpoint(entry) && isFresh(entry, now)) {
      fresh.push(entry);
    }
  }
  fresh.sort((a, b) => b.updatedAt - a.updatedAt);
  return fresh;
}

/**
 * Drop every checkpoint past the TTL. Returns the number of removed
 * entries. Safe to call on app boot; lightweight.
 */
export function pruneStaleCheckpoints(): number {
  const map = readMap();
  const now = Date.now();
  let removed = 0;
  for (const key of Object.keys(map)) {
    const entry = map[key];
    if (!isValidCheckpoint(entry) || !isFresh(entry, now)) {
      delete map[key];
      removed += 1;
    }
  }
  if (removed > 0) writeMap(map);
  return removed;
}
