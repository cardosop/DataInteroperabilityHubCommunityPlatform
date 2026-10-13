/**
 * Journey Test Helpers
 *
 * Shared assertions for Success/Failure/Edge dimensions in journey specs.
 * Used by ≥3 journey specs. No mocks/stubs; real backend only.
 *
 * Per E2E_FULL_COVERAGE_PLAN and tasks 29.1.3.
 */

import { Page, expect } from '@playwright/test';

/**
 * Assert successful page load: route reached, content visible (list, empty state, or success message).
 * Use for Success dimension in journey specs.
 *
 * @param page - Playwright page
 * @param options.successContentSelector - CSS selector(s) for expected content (comma-separated for alternatives)
 * @param options.timeout - Max wait for content (default 30s)
 */
export async function assertSuccessLoad(
  page: Page,
  options: {
    successContentSelector: string;
    timeout?: number;
  }
): Promise<void> {
  const { successContentSelector, timeout = 30000 } = options;
  await page.waitForLoadState('domcontentloaded');
  const combinedSelector = successContentSelector
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .join(', ');
  await expect(page.locator(combinedSelector).first()).toBeVisible({ timeout });
}

/**
 * Assert failure redirect: unauthenticated or forbidden access redirects to /login or /403.
 * Use for Failure dimension in journey specs.
 *
 * @param page - Playwright page
 * @param options.expectedPaths - Path patterns to accept (default: /login, /403)
 * @param options.timeout - Max wait for redirect (default 15s)
 */
export async function assertFailureRedirect(
  page: Page,
  options: {
    expectedPaths?: (string | RegExp)[];
    timeout?: number;
  } = {}
): Promise<void> {
  const { expectedPaths = [/\/login/, /\/403/] } = options;
  await page.waitForLoadState('domcontentloaded');
  // Wait for redirect to complete via URL pattern match instead of fixed timeout
  const patterns = expectedPaths.map((p) => (typeof p === 'string' ? new RegExp(p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) : p));
  const combinedPattern = new RegExp(patterns.map((p) => p.source).join('|'));
  try {
    await page.waitForURL(combinedPattern, { timeout: options.timeout ?? 15000 });
  } catch {
    // intentional: journey-helpers wraps optional-route navigation; on failure the calling spec falls back to direct goto and re-asserts via its own content selectors.
    // URL didn't match — fall through to assertion which will produce a clear error message
  }
  const url = page.url();
  const matches = expectedPaths.some((p) =>
    typeof p === 'string' ? url.includes(p) : p.test(url)
  );
  expect(matches, `Expected redirect to one of ${expectedPaths.map(String).join(', ')}, got ${url}`).toBe(true);
}

/**
 * Assert edge behavior: empty state, loading completed, or boundary condition handled.
 * Use for Edge dimension in journey specs.
 *
 * @param page - Playwright page
 * @param options.emptyStateSelector - Selector for empty state (default: .empty-state, [data-testid="empty-state"])
 * @param options.orContentSelector - Alternative: success content when not empty
 * @param options.timeout - Max wait (default 30s)
 */
export async function assertEdgeBehavior(
  page: Page,
  options: {
    emptyStateSelector?: string;
    orContentSelector?: string;
    timeout?: number;
  } = {}
): Promise<void> {
  const {
    emptyStateSelector = '.empty-state, [data-testid="empty-state"]',
    orContentSelector,
    timeout = 30000,
  } = options;
  await page.waitForLoadState('domcontentloaded');
  // Wait briefly for the empty state instead of checking once: an instant
  // count races the list fetch (isLoading renders a skeleton), and a
  // slow-but-empty fetch strands this helper on the content branch,
  // waiting for a table that never renders for an empty list (b7:
  // files.spec edge test timed out exactly this way).
  // intentional: bounded best-effort probe — falling through to the content/fallback branches below is the designed behaviour when no empty state renders.
  const hasEmpty = await page
    .locator(emptyStateSelector)
    .first()
    .waitFor({ state: 'visible', timeout: 5000 })
    .then(() => true)
    .catch(() => false);
  if (hasEmpty) {
    await expect(page.locator(emptyStateSelector).first()).toBeVisible({ timeout: 5000 });
    return;
  }
  // Churn recovery: the list fetch can die during an API restart window and
  // render ErrorDisplay ("Failed to load …", NETWORK_ERROR) with a Retry
  // affordance — neither the empty state nor the content selector matches
  // that terminal (b7: files.spec edge test burned its full 30s waiting for
  // a table that could not render). Use the app's retry ONCE, then re-probe
  // the empty state before falling through to the content branch; a
  // sustained outage then fails the content assertion with the visible state.
  const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
  const hasErrorDisplay = (await errorDisplay.count()) > 0;
  if (hasErrorDisplay) {
    const errorRetry = page.locator('[data-testid="error-display-retry"]').first();
    // intentional: diagnostic-only read — an empty read just skips the
    // retry and the strict assertions below report the visible state.
    const errorText = (await errorDisplay.textContent().catch(() => '')) ?? '';
    // intentional: retry only when the error is transient churn — a real
    // product error falls through to the strict content assertion below
    // instead of looping on a retry that cannot help.
    if (
      (await errorRetry.count()) > 0 &&
      /NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE/i.test(errorText)
    ) {
      // intentional: the retry click is best-effort — a mid-outage refetch
      // may fail again; the bounded probes below decide the verdict.
      await errorRetry.click().catch(() => null);
      // intentional: bounded best-effort probe — falling through to the
      // content branch below is the designed behaviour when no empty
      // state renders after the retry.
      const hasEmptyAfterRetry = await page
        .locator(emptyStateSelector)
        .first()
        .waitFor({ state: 'visible', timeout: 5000 })
        .then(() => true)
        .catch(() => false);
      if (hasEmptyAfterRetry) {
        await expect(page.locator(emptyStateSelector).first()).toBeVisible({ timeout: 5000 });
        return;
      }
    }
  }
  if (orContentSelector) {
    await expect(page.locator(orContentSelector).first()).toBeVisible({ timeout });
    return;
  }
  // Fallback: page loaded without crash (no 500, no error display)
  const hasError = (await page.locator('.error-display, [data-testid="error-display"], text=/500|internal server error/i').count()) > 0;
  expect(hasError, 'Edge case: page should not show error display or 500').toBe(false);
}
