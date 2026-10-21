/**
 * KYB review-queue payload normalization (Phase 1.5).
 *
 * Kept out of ``KYBReviewQueuePage.tsx`` so the component file exports only
 * the component (react-refresh/only-export-components). ``StuckAccount`` is
 * DEFINED here — the component imports it from this module; the previous
 * circular import (normalize -> page -> normalize) broke ``tsc -b``.
 */
export interface StuckAccount {
  id: string;
  stripe_account_id: string;
  tenant_id: string;
  tenant_name: string;
  country: string;
  details_submitted: boolean;
  charges_enabled: boolean;
  payouts_enabled: boolean;
  currently_due: string[];
  past_due: string[];
  created_at: string;
  hours_stuck: number;
}

export interface ReviewQueueResponse {
  results: StuckAccount[];
  count: number;
}

/**
 * Normalize the review-queue payload at the data boundary (Phase 1.5).
 *
 * The page renders ``results.map``; a 200 whose body is NOT the expected
 * ``{results: [...], count: n}`` (proxy error envelope, schema drift) used
 * to put a non-array into state and crash the render with
 * "results.map is not a function" — the ``tenants.find`` class. Exported so
 * the normalization contract is unit-pinned.
 */
export function normalizeReviewQueuePayload(payload: unknown): ReviewQueueResponse {
  const data = (payload ?? {}) as Partial<ReviewQueueResponse>;
  return {
    results: Array.isArray(data.results) ? data.results : [],
    count: typeof data.count === 'number' ? data.count : 0,
  };
}
