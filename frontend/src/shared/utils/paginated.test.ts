/**
 * Paginated-response normalization helper tests (Phase 1.5 follow-up).
 *
 * These helpers are the single choke point every paginated hook/service
 * normalizes through; pin their behaviour so the sweep's guarantee —
 * consumers always see an array — has one tested implementation.
 */
import { describe, expect, it } from 'vitest';

import { normalizePaginated, unwrapResults } from './paginated';

describe('unwrapResults', () => {
  it('passes a bare array through', () => {
    const items = [{ id: 1 }, { id: 2 }];
    expect(unwrapResults(items)).toEqual(items);
  });

  it('unwraps a paginated envelope', () => {
    const items = [{ id: 1 }];
    expect(unwrapResults({ count: 1, results: items })).toEqual(items);
  });

  it('returns [] for a non-array results key', () => {
    expect(unwrapResults({ results: { id: 1 } })).toEqual([]);
  });

  it('returns [] for a null / undefined / error payload', () => {
    expect(unwrapResults(null)).toEqual([]);
    expect(unwrapResults(undefined)).toEqual([]);
    expect(unwrapResults({ error: 'proxy exploded' })).toEqual([]);
  });
});

describe('normalizePaginated', () => {
  it('passes a well-formed envelope through untouched', () => {
    const envelope = { count: 2, page: 1, results: [{ id: 1 }, { id: 2 }] };
    expect(normalizePaginated(envelope)).toEqual(envelope);
  });

  it('fills a missing results key with [] while keeping metadata', () => {
    expect(normalizePaginated({ count: 5 })).toEqual({ count: 5, results: [] });
  });

  it('replaces a non-array results value with []', () => {
    expect(normalizePaginated({ count: 1, results: 'nope' })).toEqual({
      count: 1,
      results: [],
    });
  });

  it('turns a null payload into an empty envelope', () => {
    expect(normalizePaginated(null)).toEqual({ results: [] });
  });
});
