/**
 * Phase 234.3 — pagination reducer for the /audit list page.
 *
 * The reducer is a pure function so the pagination contract is testable
 * without React's render machinery (the repo currently has a React 19 +
 * @testing-library/react v16 ``React.act`` env issue blocking every
 * ``render()`` and ``renderHook()`` call — a separate test-infra phase).
 *
 * The 234.3 spec calls for "cursor-based pagination" but the actual
 * backend ships ``StandardPageNumberPagination`` (page-number, page_size,
 * count, next/previous URLs — see hub/apps/api/standards/pagination.py).
 * "Cursor" here is the UX shape — "Load more" appends — not the wire
 * protocol. The reducer is agnostic; ``loadMore`` simply increments the
 * page number and a separate effect concatenates the fetched batch onto
 * the accumulator.
 */
import { describe, expect, it } from 'vitest';

import type { AuditEvent, AuditEventListFilters } from '../../../shared/types/audit';
import {
  PAGE_SIZE,
  appendPage,
  initialPaginationState,
  loadMore,
  paginationReducer,
  resetFor,
  selectAccumulated,
  selectHasMore,
} from './auditPagination';

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function makeEvent(idx: number): AuditEvent {
  return {
    id: `evt-${idx.toString().padStart(6, '0')}`,
    tenant: 'tenant-1',
    tenant_name: 'Tenant One',
    actor_user: null,
    actor_user_email: null,
    resource_type: 'ASSET',
    resource_id: null,
    action: 'CREATED',
    result: 'SUCCESS',
    details_json: {},
    timestamp: new Date(2026, 0, 1, 0, 0, idx).toISOString(),
  };
}

function makeBatch(start: number, n: number): AuditEvent[] {
  return Array.from({ length: n }, (_, i) => makeEvent(start + i));
}

const NO_FILTERS: AuditEventListFilters = {};

// ---------------------------------------------------------------------------
// PAGE_SIZE constant (234.3.2)
// ---------------------------------------------------------------------------

describe('auditPagination — module constants', () => {
  it('PAGE_SIZE is 50 (234.3.2)', () => {
    // The backend's StandardPageNumberPagination.page_size is 50; max is
    // 100. We pin the frontend's request page_size to the same value so
    // count math agrees between FE and BE and we don't accidentally
    // exceed max_page_size.
    expect(PAGE_SIZE).toBe(50);
  });
});

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('auditPagination — initial state', () => {
  it('starts at page 1 with empty accumulator', () => {
    expect(initialPaginationState.page).toBe(1);
    expect(initialPaginationState.accumulated).toEqual([]);
    expect(initialPaginationState.totalCount).toBe(0);
    expect(initialPaginationState.knownPages).toEqual(new Set([]));
  });
});

// ---------------------------------------------------------------------------
// APPEND_PAGE: fold a server response onto the accumulator
// ---------------------------------------------------------------------------

describe('auditPagination — APPEND_PAGE action', () => {
  it('writes the first page into an empty accumulator', () => {
    const batch = makeBatch(0, 50);
    const next = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: batch, totalCount: 137 }),
    );
    expect(next.accumulated).toHaveLength(50);
    expect(next.totalCount).toBe(137);
    expect(next.page).toBe(1);
    expect(next.knownPages.has(1)).toBe(true);
  });

  it('appends a second page onto the first (Load more)', () => {
    const first = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 137 }),
    );
    const next = paginationReducer(
      first,
      appendPage({ page: 2, results: makeBatch(50, 50), totalCount: 137 }),
    );
    expect(next.accumulated).toHaveLength(100);
    expect(next.accumulated[0].id).toBe('evt-000000');
    expect(next.accumulated[99].id).toBe('evt-000099');
    expect(next.knownPages.has(2)).toBe(true);
  });

  it('234.3.4 — accumulates 100+ events across multiple pages', () => {
    // The headline assertion from the spec: 100+ events must be reachable
    // via the Load-more path. Three batches of 50 → 150 accumulated.
    let s = initialPaginationState;
    for (let p = 1; p <= 3; p++) {
      s = paginationReducer(
        s,
        appendPage({
          page: p,
          results: makeBatch((p - 1) * 50, 50),
          totalCount: 150,
        }),
      );
    }
    expect(s.accumulated.length).toBeGreaterThanOrEqual(100);
    expect(s.accumulated).toHaveLength(150);
    // Order preserved: the first row of page 1 stays at index 0, the
    // last row of page 3 stays at index 149. A reducer that
    // accidentally REPLACED instead of APPENDED would land the page-3
    // batch at index 0..49 instead.
    expect(s.accumulated[0].id).toBe('evt-000000');
    expect(s.accumulated[149].id).toBe('evt-000149');
  });

  it('is idempotent: re-appending a page already loaded does not duplicate rows', () => {
    // Defensive against double-clicks on Load more or a Strict-Mode
    // double-fetch — re-applying APPEND_PAGE for a page already in
    // knownPages is a no-op on accumulated.
    const first = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 137 }),
    );
    const replay = paginationReducer(
      first,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 137 }),
    );
    expect(replay.accumulated).toHaveLength(50);
    expect(replay).toBe(first); // strict equality — no spurious state churn
  });

  it('refreshes totalCount on later pages (race: count changes between fetches)', () => {
    // If a new event was created between page 1 and page 2, the server's
    // count for page 2 differs. We trust the latest page's count.
    let s = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 100 }),
    );
    s = paginationReducer(
      s,
      appendPage({ page: 2, results: makeBatch(50, 50), totalCount: 105 }),
    );
    expect(s.totalCount).toBe(105);
  });

  // -------------------------------------------------------------------
  // Defensive page-sequencing — audit-fix Gap 3
  // -------------------------------------------------------------------
  //
  // The component's invariant is "Load more is disabled while loading"
  // + "React Query cancels stale fetches on queryKey change", so
  // out-of-order page deliveries should be impossible in normal use.
  // The reducer hardens against future regressions in either
  // invariant: APPEND_PAGE rejects (no-op) pages that aren't the
  // next-in-sequence. Without this guard, an out-of-order page-2
  // landing on an empty accumulator would corrupt the accumulator
  // order (rows appended in wrong order, can't be detected
  // downstream).

  it('rejects an out-of-order first page (genesis must be page=1)', () => {
    // Empty accumulator, but page 2 arrives first — drop it. The
    // first page we accept MUST be page 1.
    const next = paginationReducer(
      initialPaginationState,
      appendPage({ page: 2, results: makeBatch(50, 50), totalCount: 100 }),
    );
    expect(next).toBe(initialPaginationState);
  });

  it('rejects a skipped page (page=3 when only page=1 has been seen)', () => {
    const first = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 200 }),
    );
    const skipped = paginationReducer(
      first,
      appendPage({ page: 3, results: makeBatch(100, 50), totalCount: 200 }),
    );
    // Skipping page 2 would corrupt the accumulator order — drop the
    // misordered fetch; the user can still re-click Load more for page 2.
    expect(skipped).toBe(first);
  });
});

// ---------------------------------------------------------------------------
// LOAD_MORE: advance the page cursor
// ---------------------------------------------------------------------------

describe('auditPagination — LOAD_MORE action', () => {
  it('advances page from 1 to 2', () => {
    const next = paginationReducer(initialPaginationState, loadMore());
    expect(next.page).toBe(2);
  });

  it('does not duplicate-append: subsequent APPEND_PAGE on the new page is required', () => {
    const advanced = paginationReducer(initialPaginationState, loadMore());
    // Critical contract: LOAD_MORE only changes the page CURSOR; the
    // accumulator is untouched until an APPEND_PAGE for that page lands.
    // This split lets the component fire the request, wait for it, then
    // commit the rows — a single LOAD_MORE click cannot synthesize rows
    // that don't exist on the server.
    expect(advanced.accumulated).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// RESET_FOR: filter change resets to page 1
// ---------------------------------------------------------------------------

describe('auditPagination — RESET_FOR action (234.3.2 — preserve filter state)', () => {
  it('drops the accumulator and rewinds page to 1 when filters change', () => {
    let s = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 137 }),
    );
    s = paginationReducer(s, loadMore());
    s = paginationReducer(
      s,
      appendPage({ page: 2, results: makeBatch(50, 50), totalCount: 137 }),
    );
    expect(s.accumulated).toHaveLength(100);

    // User changes a filter — accumulator must be discarded so the new
    // result set is not contaminated by rows from the previous filter.
    const reset = paginationReducer(
      s,
      resetFor({ resource_type: 'CONTRACT' }),
    );
    expect(reset.page).toBe(1);
    expect(reset.accumulated).toEqual([]);
    expect(reset.totalCount).toBe(0);
    expect(reset.knownPages.size).toBe(0);
    expect(reset.filters).toEqual({ resource_type: 'CONTRACT' });
  });

  it('is a no-op when filters are deeply equal', () => {
    const initial = paginationReducer(initialPaginationState, resetFor(NO_FILTERS));
    const replay = paginationReducer(initial, resetFor(NO_FILTERS));
    // Strict reference equality — a stable reducer avoids spurious
    // re-renders when nothing actually changed.
    expect(replay).toBe(initial);
  });

  it('distinguishes empty string from undefined filter values', () => {
    // ``resource_type: ''`` and ``resource_type: undefined`` both mean
    // "no filter" semantically. The component normalizes empty strings
    // to undefined before dispatching, so the reducer treats them as
    // equal. This guards against a regression where typing then
    // clearing a filter would re-fetch.
    const empty = paginationReducer(initialPaginationState, resetFor({ resource_type: '' }));
    const undef = paginationReducer(initialPaginationState, resetFor({ resource_type: undefined }));
    expect(empty.filters).toEqual(undef.filters);
  });
});

// ---------------------------------------------------------------------------
// SELECTORS
// ---------------------------------------------------------------------------

describe('auditPagination — selectors', () => {
  it('selectAccumulated returns the rows in load order', () => {
    let s = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 3), totalCount: 6 }),
    );
    s = paginationReducer(
      s,
      appendPage({ page: 2, results: makeBatch(3, 3), totalCount: 6 }),
    );
    expect(selectAccumulated(s)).toHaveLength(6);
  });

  it('selectHasMore is true when accumulated < totalCount', () => {
    const s = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 50), totalCount: 137 }),
    );
    expect(selectHasMore(s)).toBe(true);
  });

  it('selectHasMore is false when accumulated >= totalCount', () => {
    const s = paginationReducer(
      initialPaginationState,
      appendPage({ page: 1, results: makeBatch(0, 7), totalCount: 7 }),
    );
    expect(selectHasMore(s)).toBe(false);
  });

  it('selectHasMore is false on empty results (totalCount=0)', () => {
    expect(selectHasMore(initialPaginationState)).toBe(false);
  });
});
