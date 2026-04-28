/**
 * `verifySearchable` — search-index freshness guarantee (Phase 226 G12).
 *
 * Cross-channel check that asserts a freshly-mutated resource appears in
 * the unified search index within a bounded poll window. The platform
 * promise is: "after a successful create, the resource is queryable via
 * `/api/v1/search/search/?q={key}&type={resourceType}`". A regression in
 * indexer plumbing (e.g. signal handler dropped, reindex Celery task
 * failing silently) is otherwise invisible to UI specs that only verify
 * the detail page renders.
 *
 * Pure logic split out so `_guards.spec.ts` can unit-test every branch
 * without a browser:
 *   - `findInSearchResults(rows, expected)` — matcher only.
 *   - `pollForSearchResult(fetcher, expected)` — retry loop with injected
 *     fetcher.
 *
 * The browser-facing `verifySearchable(page, expected)` wires
 * `page.request.get` into `pollForSearchResult` and carries Bearer-token
 * extraction.
 */

import type { Page } from '@playwright/test';

/** Resource types the unified search index understands. Matches the
 * backend `SearchService.search(resource_type=...)` contract. */
export type SearchResourceType =
  | 'ASSET'
  | 'DATASET'
  | 'CONTRACT'
  | 'LISTING'
  | (string & {});

/** Row shape returned by `/api/v1/search/search/?q=...`. The exact field
 * set depends on the resource type but every row carries `id` and
 * `resource_type`. The optional `key` and `name` fields are how the
 * matcher verifies it's the right row (not just any row of that type). */
export interface SearchResultRow {
  id: string;
  resource_type?: string;
  type?: string;
  key?: string;
  name?: string;
  title?: string;
  // Allow forward-compat fields without TS friction.
  [extra: string]: unknown;
}

export interface SearchExpectation {
  /** Resource type filter passed to the API as `?type=`. */
  resourceType: SearchResourceType;
  /** The resource id that MUST appear in the result rows. */
  id: string;
  /** Search query string passed to the API as `?q=`. Typically the
   * resource's stable key, slug, or title — anything that uniquely picks
   * the new row out of the index. */
  key: string;
}

export interface PollOptions {
  /** Total time budget across all attempts. Default 20_000 ms — covers
   * both the synchronous indexer path and Celery-delayed reindex. */
  retryBudgetMs?: number;
  /** Interval between attempts. Default 1_000 ms. */
  pollIntervalMs?: number;
}

export interface VerifySearchableOptions extends PollOptions {
  /** Override the auth extraction. Rarely needed. */
  authHeaderOverride?: Record<string, string>;
  /** Override the search endpoint. Default `/api/v1/search/search/`. */
  searchEndpoint?: string;
}

export interface FindResult {
  matched: SearchResultRow | null;
  /** Diagnostic message when `matched === null`. Includes the closest-id
   * miss so the next-runner sees "why not" without fetching the body. */
  mismatch: string | null;
}

/**
 * Pure matcher. Given a list of rows and an expectation, returns the row
 * whose `id` equals `expected.id`, or a mismatch message otherwise.
 *
 * Branches:
 *   - 0 rows  → "0 results returned"
 *   - N rows, none match → "N rows; none had id=..."
 *   - N rows, one matches → returns it
 */
export function findInSearchResults(
  rows: readonly SearchResultRow[],
  expected: SearchExpectation,
): FindResult {
  if (rows.length === 0) {
    return {
      matched: null,
      mismatch:
        `no matching search row: 0 results returned for ` +
        `q=${expected.key} type=${expected.resourceType}.`,
    };
  }
  const match = rows.find((row) => row.id === expected.id);
  if (match) return { matched: match, mismatch: null };

  const ids = rows.map((r) => r.id).slice(0, 10);
  return {
    matched: null,
    mismatch:
      `no matching search row among ${rows.length} candidate row${rows.length === 1 ? '' : 's'}. ` +
      `Expected id=${expected.id}; saw ids=[${ids.join(', ')}].`,
  };
}

export type SearchFetcher = () => Promise<readonly SearchResultRow[]>;

/**
 * Retry loop. Repeatedly invokes `fetcher` until either a row matching
 * `expected.id` appears or the budget exhausts. Throws on exhaustion with
 * a diagnostic message naming the last mismatch.
 */
export async function pollForSearchResult(
  fetcher: SearchFetcher,
  expected: SearchExpectation & PollOptions,
): Promise<SearchResultRow> {
  const retryBudgetMs = expected.retryBudgetMs ?? 20_000;
  const pollIntervalMs = expected.pollIntervalMs ?? 1_000;
  const deadline = Date.now() + retryBudgetMs;

  let lastMismatch = 'no attempts made (0 ms budget?)';

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const rows = await fetcher();
    const result = findInSearchResults(rows, expected);
    if (result.matched) return result.matched;
    lastMismatch = result.mismatch ?? lastMismatch;

    if (Date.now() >= deadline) break;

    const remaining = deadline - Date.now();
    const sleepMs = Math.min(pollIntervalMs, Math.max(0, remaining));
    await new Promise((resolve) => setTimeout(resolve, sleepMs));
    if (Date.now() >= deadline) {
      const finalRows = await fetcher();
      const finalResult = findInSearchResults(finalRows, expected);
      if (finalResult.matched) return finalResult.matched;
      lastMismatch = finalResult.mismatch ?? lastMismatch;
      break;
    }
  }

  throw new Error(
    `verifySearchable: exhausted ${retryBudgetMs} ms budget without finding row in search index. ${lastMismatch}`,
  );
}

async function extractBearerHeaders(
  page: Page,
  override?: Record<string, string>,
): Promise<Record<string, string>> {
  if (override !== undefined) return override;
  const token = await page.evaluate<string | null>(
    () =>
      (globalThis as unknown as { localStorage?: { getItem: (k: string) => string | null } })
        .localStorage?.getItem('access_token') ?? null,
  );
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Browser-facing helper. Composes header extraction + fetcher + retry loop
 * into a single one-liner for specs:
 *
 *   await verifySearchable(page, {
 *     resourceType: 'ASSET',
 *     id: assetId,
 *     key: assetKey,
 *   });
 *
 * The default 20-second budget tolerates both synchronous indexers and
 * the Celery-delayed reindex path. Tune via `retryBudgetMs` if needed.
 */
export async function verifySearchable(
  page: Page,
  expected: SearchExpectation,
  options: VerifySearchableOptions = {},
): Promise<SearchResultRow> {
  const headers = await extractBearerHeaders(page, options.authHeaderOverride);
  const endpoint = options.searchEndpoint ?? '/api/v1/search/search/';
  const params = new URLSearchParams({
    q: expected.key,
    type: expected.resourceType,
    limit: '20',
  });
  const url = `${endpoint}?${params.toString()}`;

  const fetcher: SearchFetcher = async () => {
    const res = await page.request.get(url, { headers });
    if (!res.ok()) {
      let preview = '';
      try {
        preview = (await res.text()).slice(0, 400);
      } catch {
        /* ignore — preview is best-effort */
      }
      throw new Error(
        `verifySearchable: GET ${url} returned ${res.status()}. Body preview: ${preview}`,
      );
    }
    const body = (await res.json()) as { results?: SearchResultRow[] } | SearchResultRow[];
    if (Array.isArray(body)) return body;
    return body.results ?? [];
  };

  return pollForSearchResult(fetcher, {
    ...expected,
    retryBudgetMs: options.retryBudgetMs,
    pollIntervalMs: options.pollIntervalMs,
  });
}
