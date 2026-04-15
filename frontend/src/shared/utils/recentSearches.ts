/**
 * recentSearches — 223.6.1.
 *
 * localStorage-backed helper for the SearchPage's "recent searches"
 * dropdown. Keeps the last 10 non-empty, deduplicated queries with
 * ISO-8601 timestamps (newest first).
 *
 * All I/O is wrapped in try/except so a full-storage or privacy-mode
 * browser never crashes the search page — a failed read yields `[]` and
 * a failed write is silently dropped. Corrupt JSON or malformed array
 * entries are defensively filtered rather than thrown, because a stale
 * key from an older schema shouldn't brick the current feature.
 */

export const RECENT_SEARCH_STORAGE_KEY = 'meshant.search.recent';
export const MAX_RECENT_SEARCHES = 10;

export interface RecentSearchEntry {
  query: string;
  /** ISO-8601 timestamp of the last recording. */
  timestamp: string;
}

function isEntry(value: unknown): value is RecentSearchEntry {
  return (
    !!value &&
    typeof value === 'object' &&
    typeof (value as { query?: unknown }).query === 'string' &&
    typeof (value as { timestamp?: unknown }).timestamp === 'string'
  );
}

export function getRecentSearches(): RecentSearchEntry[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const raw = localStorage.getItem(RECENT_SEARCH_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isEntry);
  } catch {
    return [];
  }
}

export function recordSearch(query: string): void {
  const trimmed = query.trim();
  if (!trimmed) return;
  const entry: RecentSearchEntry = {
    query: trimmed,
    timestamp: new Date().toISOString(),
  };
  const existing = getRecentSearches().filter((e) => e.query !== trimmed);
  const next = [entry, ...existing].slice(0, MAX_RECENT_SEARCHES);
  try {
    localStorage.setItem(RECENT_SEARCH_STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* storage full / disabled — silent */
  }
}

export function clearRecentSearches(): void {
  try {
    localStorage.removeItem(RECENT_SEARCH_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
