/**
 * Phase 234.3 — pagination state machine for the /audit list page.
 *
 * Why a reducer (instead of inline ``useState``)?
 * ----------------------------------------------
 * The Load-more contract has multi-field transitions (page cursor,
 * accumulator, total-count, known-pages set, current filter snapshot)
 * that must move together to stay consistent. Encoding them as a pure
 * reducer:
 *
 *   * Makes every transition unit-testable without React's render
 *     machinery (the repo currently has a React 19 +
 *     ``@testing-library/react`` v16 ``React.act`` env issue that
 *     blocks ``render()`` and ``renderHook()`` — separate test-infra
 *     phase). The reducer is plain TS, no DOM, no jsdom.
 *   * Eliminates the entire class of bugs where one of the fields
 *     advances and another doesn't (e.g. ``page`` increments but the
 *     accumulator is wiped → user sees no rows).
 *   * Plays nicely with ``useReducer`` in the component: the wire-up
 *     is a dozen lines.
 *
 * Wire protocol vs UX
 * -------------------
 * The 234.3 spec asks for "cursor-based pagination". The backend ships
 * ``StandardPageNumberPagination`` (offset/page-number; see
 * ``hub/apps/api/standards/pagination.py``). "Cursor" here is the UX
 * shape — "Load more" appends — not the wire protocol. The reducer
 * works against page numbers because that's what the API returns
 * (count + next/previous URLs + page). Switching to a real cursor
 * field would change the wire shape on every audit-list consumer and
 * is out of 234.3 scope.
 *
 * Idempotency
 * -----------
 * ``APPEND_PAGE`` is idempotent on a page already loaded: re-applying
 * the same page (double-click on Load more, StrictMode double-fetch,
 * etc.) does not duplicate rows. The reducer returns the exact same
 * state reference, so a downstream ``useReducer`` consumer doesn't
 * re-render unnecessarily.
 */
import type { AuditEvent, AuditEventListFilters } from '../../../shared/types/audit';

/** Aligned with backend ``StandardPageNumberPagination.page_size`` (50). */
export const PAGE_SIZE = 50;

// ---------------------------------------------------------------------------
// Filter normalization — empty strings collapse to undefined
// ---------------------------------------------------------------------------

/**
 * Normalize filters so empty strings and undefined are treated as the same
 * "no filter" value. The component's controlled inputs default to ``""``
 * when cleared; comparing those against an ``undefined`` upstream value
 * would otherwise look like a filter CHANGE and trigger a spurious reset.
 */
function normalizeFilters(filters: AuditEventListFilters): AuditEventListFilters {
  const out: AuditEventListFilters = {};
  for (const [key, value] of Object.entries(filters) as [
    keyof AuditEventListFilters,
    AuditEventListFilters[keyof AuditEventListFilters],
  ][]) {
    if (value === '' || value === undefined || value === null) continue;
    // ``page`` / ``page_size`` are managed by the reducer itself, not by
    // the caller — drop them defensively so a stale value can't override.
    if (key === 'page' || key === 'page_size') continue;
    (out as Record<string, unknown>)[key] = value;
  }
  return out;
}

function filtersEqual(
  a: AuditEventListFilters,
  b: AuditEventListFilters,
): boolean {
  const aKeys = Object.keys(a).sort();
  const bKeys = Object.keys(b).sort();
  if (aKeys.length !== bKeys.length) return false;
  if (aKeys.some((k, i) => k !== bKeys[i])) return false;
  return aKeys.every(
    (k) =>
      (a as Record<string, unknown>)[k] ===
      (b as Record<string, unknown>)[k],
  );
}

// ---------------------------------------------------------------------------
// State + actions
// ---------------------------------------------------------------------------

export interface PaginationState {
  /** Next page number to request (1-based). After a clean start, 1. */
  page: number;
  /** All rows loaded so far, in the order the server returned them. */
  accumulated: AuditEvent[];
  /** Server-reported total across all pages for the active filter set. */
  totalCount: number;
  /**
   * Pages already folded into ``accumulated``. Used to make
   * ``APPEND_PAGE`` idempotent.
   */
  knownPages: Set<number>;
  /** Normalized filter snapshot the accumulator was built against. */
  filters: AuditEventListFilters;
}

export const initialPaginationState: PaginationState = {
  page: 1,
  accumulated: [],
  totalCount: 0,
  knownPages: new Set<number>(),
  filters: {},
};

export type PaginationAction =
  | { type: 'APPEND_PAGE'; payload: AppendPagePayload }
  | { type: 'LOAD_MORE' }
  | { type: 'RESET_FOR'; payload: { filters: AuditEventListFilters } };

export interface AppendPagePayload {
  page: number;
  results: AuditEvent[];
  totalCount: number;
}

export function appendPage(payload: AppendPagePayload): PaginationAction {
  return { type: 'APPEND_PAGE', payload };
}

export function loadMore(): PaginationAction {
  return { type: 'LOAD_MORE' };
}

export function resetFor(filters: AuditEventListFilters): PaginationAction {
  return { type: 'RESET_FOR', payload: { filters: normalizeFilters(filters) } };
}

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

export function paginationReducer(
  state: PaginationState,
  action: PaginationAction,
): PaginationState {
  switch (action.type) {
    case 'APPEND_PAGE': {
      const { page, results, totalCount } = action.payload;
      if (state.knownPages.has(page)) {
        // Idempotent — same reference so consumers don't re-render.
        return state;
      }
      // Defensive page-sequencing (audit-fix Gap 3). The component's
      // invariants make out-of-order deliveries unreachable in normal
      // use (Load-more button disabled while loading + React Query
      // cancels stale fetches on queryKey change). But a future
      // regression in EITHER invariant — e.g. someone adds prefetching
      // or forgets the disabled state — would silently corrupt the
      // accumulator's row order. Hardening here makes the reducer
      // refuse any APPEND_PAGE that isn't the next sequential page;
      // the bad fetch is dropped (same-reference return), the
      // component can re-click Load more, and the contract holds.
      const expectedNextPage = state.accumulated.length === 0
        ? 1
        : Math.max(...state.knownPages) + 1;
      if (page !== expectedNextPage) {
        return state;
      }
      const nextKnown = new Set(state.knownPages);
      nextKnown.add(page);
      return {
        ...state,
        // The latest fetch wins on totalCount — events created between
        // fetches shift the count, and we trust the most-recent server
        // observation. ``selectHasMore`` reads this to decide whether
        // to render the Load-more button.
        totalCount,
        accumulated: state.accumulated.concat(results),
        knownPages: nextKnown,
        // ``page`` stays at the cursor the next request should use.
        // After LOAD_MORE advanced it, APPEND_PAGE for that cursor is
        // the commit step — the cursor itself is unchanged here.
      };
    }
    case 'LOAD_MORE': {
      return { ...state, page: state.page + 1 };
    }
    case 'RESET_FOR': {
      const next = action.payload.filters;
      if (filtersEqual(state.filters, next) && state.page === 1 && state.accumulated.length === 0) {
        return state;
      }
      return {
        ...initialPaginationState,
        knownPages: new Set<number>(),
        filters: next,
      };
    }
    default: {
      // Exhaustive narrowing — TS will flag any new action that forgets
      // to add a case here.
      const _exhaustive: never = action;
      void _exhaustive;
      return state;
    }
  }
}

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

export function selectAccumulated(state: PaginationState): AuditEvent[] {
  return state.accumulated;
}

export function selectHasMore(state: PaginationState): boolean {
  // ``totalCount === 0`` covers both empty result sets and the
  // genuinely-no-data initial state. Either way, no Load-more button.
  if (state.totalCount === 0) return false;
  return state.accumulated.length < state.totalCount;
}
