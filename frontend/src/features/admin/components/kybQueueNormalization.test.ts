/**
 * KYB review-queue payload normalization (Phase 1.5).
 *
 * The backend contract is ``{results: [...], count: n}``. A 200 carrying a
 * different shape (proxy error envelope, drift) used to put a non-array
 * into ``results`` state and crash the render at ``results.map`` — the
 * ``tenants.find`` class. Pins the boundary normalization exported from the
 * page module.
 */
import { describe, expect, it } from 'vitest';

import { normalizeReviewQueuePayload } from './kybReviewQueueNormalize';

const ACCOUNTS = [
  { id: 'a1', stripe_account_id: 'acct_1' },
  { id: 'a2', stripe_account_id: 'acct_2' },
];

describe('normalizeReviewQueuePayload', () => {
  it('passes the contract shape through unchanged', () => {
    expect(normalizeReviewQueuePayload({ results: ACCOUNTS, count: 2 })).toEqual({
      results: ACCOUNTS,
      count: 2,
    });
  });

  it('normalizes a missing results key to [] and count to 0', () => {
    expect(normalizeReviewQueuePayload({ count: 5 })).toEqual({ results: [], count: 5 });
  });

  it('normalizes a non-array results value to []', () => {
    expect(normalizeReviewQueuePayload({ results: { a1: true }, count: 1 })).toEqual({
      results: [],
      count: 1,
    });
  });

  it('normalizes a proxy error envelope to the empty queue', () => {
    expect(normalizeReviewQueuePayload({ error: 'proxy exploded', detail: 'boom' })).toEqual({
      results: [],
      count: 0,
    });
  });

  it('normalizes a null body to the empty queue', () => {
    expect(normalizeReviewQueuePayload(null)).toEqual({ results: [], count: 0 });
  });
});
