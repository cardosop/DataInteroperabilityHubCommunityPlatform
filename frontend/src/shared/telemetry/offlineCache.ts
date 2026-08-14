/**
 * 281.B.7.2 — Offline IndexedDB cache for recently viewed content.
 *
 * Caches API responses in IndexedDB so recently viewed assets, contracts,
 * and marketplace listings are available offline or on flaky connections.
 * Pending writes (mutations while offline) are queued for background sync
 * when connectivity returns.
 */
const DB_NAME = 'meshant-offline';
const DB_VERSION = 1;
const STORE_NAME = 'api-cache';
const QUEUE_STORE = 'write-queue';

interface CacheEntry {
  url: string;
  response: unknown;
  cachedAt: number;
  ttl: number;
}

interface QueuedWrite {
  id: string;
  url: string;
  method: string;
  body: string;
  queuedAt: number;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'url' });
      }
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** Cache an API GET response for offline use. */
export async function cacheResponse(url: string, response: unknown, ttlMs = 3600000): Promise<void> {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put({
      url, response, cachedAt: Date.now(), ttl: ttlMs,
    });
  } catch { /* offline cache is best-effort */ }
}

/** Retrieve a cached API response, or null if expired/missing. */
export async function getCachedResponse<T>(url: string): Promise<T | null> {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readonly');
    const entry: CacheEntry | undefined = await new Promise((resolve) => {
      const req = tx.objectStore(STORE_NAME).get(url);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(undefined);
    });
    if (!entry) return null;
    if (Date.now() - entry.cachedAt > entry.ttl) {
      // Expired — clean up
      db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).delete(url);
      return null;
    }
    return entry.response as T;
  } catch {
    return null;
  }
}

/** Queue a write operation for background sync when online. */
export async function queueWrite(id: string, url: string, method: string, body: string): Promise<void> {
  try {
    const db = await openDB();
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    tx.objectStore(QUEUE_STORE).put({ id, url, method, body, queuedAt: Date.now() });
  } catch { /* best-effort */ }
}

/** Process queued writes — call when connectivity is restored. */
export async function processWriteQueue(sendFn: (entry: QueuedWrite) => Promise<Response>): Promise<number> {
  try {
    const db = await openDB();
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    const entries: QueuedWrite[] = await new Promise((resolve) => {
      const req = tx.objectStore(QUEUE_STORE).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve([]);
    });

    let processed = 0;
    for (const entry of entries) {
      try {
        await sendFn(entry);
        tx.objectStore(QUEUE_STORE).delete(entry.id);
        processed++;
      } catch {
        // Leave in queue for next sync cycle
      }
    }
    return processed;
  } catch {
    return 0;
  }
}

// Register online/offline listeners for background sync
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    processWriteQueue(async (entry) => {
      const resp = await fetch(entry.url, {
        method: entry.method,
        headers: { 'Content-Type': 'application/json' },
        body: entry.method !== 'GET' ? entry.body : undefined,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp;
    });
  });
}
