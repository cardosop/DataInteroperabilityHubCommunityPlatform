/**
 * Phase 226 PR C1 — event-based wait helpers.
 *
 * `page.waitForTimeout(N)` is the dominant flake source in this suite:
 *   - Too short → race lost on a slow CI runner.
 *   - Too long  → wall-time creeps up silently across hundreds of tests.
 *
 * The helpers below replace the patterns we found by frequency in the
 * top-20 offender specs:
 *
 *   1. `await x.click(); await page.waitForTimeout(2000); await assertX();`
 *      → `await x.click(); await waitForApiResponse(page, /\/foo\//); await assertX();`
 *
 *   2. `for (...) { try { await check() } catch { await waitForTimeout(1000) } }`
 *      → `await pollUntil(check, { intervalMs: 1000, deadlineMs: 30_000 })`
 *
 *   3. `await page.click(submit); await page.waitForTimeout(1500); // settle`
 *      → `await page.click(submit); await waitForNetworkSettle(page);`
 *
 * The helpers are designed to be drop-in: same return shape as the
 * underlying Playwright API where possible, with sensible defaults so a
 * call site shrinks from 4 lines to 1.
 *
 * Pure-logic exports (predicate / extractor / formatter) live alongside
 * the I/O helpers and are unit-tested in `_guards.spec.ts`.
 */

import type { Page, Response } from '@playwright/test';

// ----------------------------------------------------------- pure logic

/**
 * Return whether a Response URL+status matches the caller's filter.
 * Pure so we can unit-test the predicate without a real Page/Response.
 */
export function matchesResponseFilter(
  url: string,
  status: number,
  filter: { urlPattern: string | RegExp; statuses?: readonly number[] },
): boolean {
  const urlMatches =
    typeof filter.urlPattern === 'string'
      ? url.includes(filter.urlPattern)
      : filter.urlPattern.test(url);
  if (!urlMatches) return false;
  if (filter.statuses && filter.statuses.length > 0) {
    return filter.statuses.includes(status);
  }
  // Default: any non-5xx is acceptable (a 5xx still indicates a backend
  // bug we want surfaced via the dual-channel guard, not silently retried).
  return status < 500;
}

/**
 * Compute the next attempt's deadline, given the elapsed time and a budget.
 * Pure so the polling helper's clamping logic can be tested without a
 * real timer.
 */
export function computePollDeadline(
  startedAtMs: number,
  budgetMs: number,
  intervalMs: number,
  nowMs: number,
): { shouldRetry: boolean; sleepMs: number } {
  const elapsed = nowMs - startedAtMs;
  if (elapsed >= budgetMs) return { shouldRetry: false, sleepMs: 0 };
  const remaining = budgetMs - elapsed;
  return { shouldRetry: true, sleepMs: Math.min(intervalMs, Math.max(0, remaining)) };
}

// ------------------------------------------------------- I/O helpers

interface WaitForApiOptions {
  /** URL substring or regex to match the response URL. */
  urlPattern: string | RegExp;
  /** Acceptable status codes; default: any < 500. */
  statuses?: readonly number[];
  /** Total budget for the wait, default 15 000 ms. */
  timeoutMs?: number;
}

/**
 * Replacement for `await page.waitForTimeout(N)` after a click that triggers
 * an API call. Returns the matched response so callers can read its body
 * for assertion. If no response arrives within `timeoutMs`, throws — the
 * caller should fix the selector or the URL pattern, not catch the error.
 *
 * Example replacement:
 *   // before
 *   await saveBtn.click();
 *   await page.waitForTimeout(2000);
 *   // after
 *   await Promise.all([
 *     waitForApiResponse(page, { urlPattern: '/api/v1/assets/', statuses: [200, 201] }),
 *     saveBtn.click(),
 *   ]);
 */
export async function waitForApiResponse(
  page: Page,
  options: WaitForApiOptions,
): Promise<Response> {
  const { timeoutMs = 15000 } = options;
  return page.waitForResponse(
    (resp) => matchesResponseFilter(resp.url(), resp.status(), options),
    { timeout: timeoutMs },
  );
}

/**
 * Wait until the network has been quiet for ~500 ms and the document is in
 * `domcontentloaded` state. Replaces the common
 *   await page.waitForLoadState('domcontentloaded');
 *   await page.waitForTimeout(1500);
 * pattern. Falls back gracefully when networkidle is over-strict (we only
 * use it as a "settle" cue; the real assertion comes after).
 */
export async function waitForNetworkSettle(
  page: Page,
  options: { timeoutMs?: number } = {},
): Promise<void> {
  const { timeoutMs = 10000 } = options;
  await page.waitForLoadState('domcontentloaded', { timeout: timeoutMs }).catch(() => {
    // already past DCL — fine.
  });
  await page.waitForLoadState('networkidle', { timeout: timeoutMs }).catch(() => {
    // networkidle is best-effort; long-poll websockets / SSE may keep it
    // busy indefinitely. Caller should follow this with an event-based
    // assertion (locator.waitFor, expect.toHaveText, etc.).
  });
}

interface PollUntilOptions {
  /** Total budget; default 30 000 ms. */
  timeoutMs?: number;
  /** Time between attempts; default 500 ms. */
  intervalMs?: number;
  /** Human-readable label for the deadline-exhausted error message. */
  label?: string;
}

/**
 * Run `predicate` repeatedly until it returns truthy or the deadline expires.
 * The intent is to retire `for (...) { try { check() } catch { wait } }` retry
 * loops, where the wait is what we're trying to delete — `pollUntil`'s
 * interval is bounded by the remaining budget so we never overshoot the
 * deadline.
 *
 * Returns the truthy value the predicate produced. Throws on timeout with
 * a label so debugging the exhausted budget points at the call site.
 *
 * Example replacement:
 *   // before
 *   let row;
 *   for (let i = 0; i < 20; i++) {
 *     row = await fetchRow();
 *     if (row) break;
 *     await page.waitForTimeout(1000);
 *   }
 *   if (!row) throw new Error('row never appeared');
 *   // after
 *   const row = await pollUntil(() => fetchRow(), {
 *     intervalMs: 1000,
 *     timeoutMs: 20_000,
 *     label: 'asset row never appeared in list',
 *   });
 */
export async function pollUntil<T>(
  predicate: () => Promise<T | null | undefined> | T | null | undefined,
  options: PollUntilOptions = {},
): Promise<T> {
  const { timeoutMs = 30000, intervalMs = 500, label = 'condition' } = options;
  const startedAt = Date.now();
  let lastError: unknown;
  while (true) {
    try {
      const value = await predicate();
      if (value !== null && value !== undefined && value !== false) {
        return value as T;
      }
    } catch (err) {
      lastError = err;
    }
    const { shouldRetry, sleepMs } = computePollDeadline(
      startedAt,
      timeoutMs,
      intervalMs,
      Date.now(),
    );
    if (!shouldRetry) {
      const errSuffix = lastError ? ` (last error: ${String(lastError)})` : '';
      throw new Error(
        `pollUntil: ${label} not satisfied within ${timeoutMs}ms${errSuffix}`,
      );
    }
    if (sleepMs > 0) {
      await new Promise<void>((resolve) => setTimeout(resolve, sleepMs));
    }
  }
}

/**
 * Wait for an element matching the locator to be visible OR hidden, with
 * a single timeout. Wrapper exists so spec authors don't have to remember
 * which Playwright API to call (`locator.waitFor` vs `page.waitForSelector`)
 * and so we have one place to change defaults.
 */
export async function waitForLocatorVisible(
  page: Page,
  selector: string,
  options: { timeoutMs?: number } = {},
): Promise<void> {
  const { timeoutMs = 15000 } = options;
  await page.locator(selector).first().waitFor({ state: 'visible', timeout: timeoutMs });
}
