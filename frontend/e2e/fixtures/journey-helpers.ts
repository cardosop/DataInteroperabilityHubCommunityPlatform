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
  const { expectedPaths = [/\/login/, /\/403/], timeout = 15000 } = options;
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000); // Allow redirect to complete
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
 * @param options.emptyStateSelector - Selector for empty state (default: .empty-state)
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
    emptyStateSelector = '.empty-state',
    orContentSelector,
    timeout = 30000,
  } = options;
  await page.waitForLoadState('domcontentloaded');
  const hasEmpty = (await page.locator(emptyStateSelector).count()) > 0;
  if (hasEmpty) {
    await expect(page.locator(emptyStateSelector).first()).toBeVisible({ timeout: 5000 });
    return;
  }
  if (orContentSelector) {
    await expect(page.locator(orContentSelector).first()).toBeVisible({ timeout });
    return;
  }
  // Fallback: page loaded without crash (no 500, no error display)
  const hasError = (await page.locator('.error-display, text=/500|internal server error/i').count()) > 0;
  expect(hasError, 'Edge case: page should not show error display or 500').toBe(false);
}
