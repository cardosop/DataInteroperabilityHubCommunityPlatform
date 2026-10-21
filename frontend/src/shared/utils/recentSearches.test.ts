/**
 * recentSearches — 223.6.1 tests.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearRecentSearches,
  getRecentSearches,
  RECENT_SEARCH_STORAGE_KEY,
  recordSearch,
} from './recentSearches';

describe('recentSearches', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it('starts empty', () => {
    expect(getRecentSearches()).toEqual([]);
  });

  it('recordSearch prepends newest entries', () => {
    recordSearch('alpha');
    recordSearch('beta');
    const recent = getRecentSearches();
    expect(recent.map((r) => r.query)).toEqual(['beta', 'alpha']);
  });

  it('timestamps each entry', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-15T12:00:00Z'));
    recordSearch('x');
    const recent = getRecentSearches();
    expect(recent[0].timestamp).toBe(
      new Date('2026-04-15T12:00:00Z').toISOString(),
    );
  });

  it('deduplicates on re-record (moves the query to the top)', () => {
    recordSearch('alpha');
    recordSearch('beta');
    recordSearch('alpha');
    const recent = getRecentSearches();
    expect(recent.map((r) => r.query)).toEqual(['alpha', 'beta']);
    expect(recent).toHaveLength(2);
  });

  it('caps history at 10 entries, newest first', () => {
    for (let i = 0; i < 15; i++) recordSearch(`q${i}`);
    const recent = getRecentSearches();
    expect(recent).toHaveLength(10);
    expect(recent[0].query).toBe('q14');
    expect(recent[9].query).toBe('q5');
  });

  it('trims whitespace and drops empty queries', () => {
    recordSearch('   ');
    recordSearch('');
    recordSearch('  alpha  ');
    const recent = getRecentSearches();
    expect(recent.map((r) => r.query)).toEqual(['alpha']);
  });

  it('clearRecentSearches empties the store', () => {
    recordSearch('alpha');
    clearRecentSearches();
    expect(getRecentSearches()).toEqual([]);
  });

  it('survives a corrupt JSON payload', () => {
    localStorage.setItem(RECENT_SEARCH_STORAGE_KEY, 'not-json');
    expect(getRecentSearches()).toEqual([]);
    recordSearch('alpha'); // still functional
    expect(getRecentSearches().map((r) => r.query)).toEqual(['alpha']);
  });

  it('survives a malformed array payload (wrong item shape)', () => {
    localStorage.setItem(
      RECENT_SEARCH_STORAGE_KEY,
      JSON.stringify(['plain string', { query: 'ok', timestamp: '2026-01-01T00:00:00Z' }]),
    );
    const recent = getRecentSearches();
    expect(recent).toHaveLength(1);
    expect(recent[0].query).toBe('ok');
  });
});
