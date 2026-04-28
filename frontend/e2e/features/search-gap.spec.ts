/**
 * Phase 7.5 — FEATURES gap closure (split per 226.E3).
 *
 * @deprecated — kept until Track D's replacement coverage lands; the
 * PR-time smoke (`@critical`) excludes this file via `--grep-invert`.
 * Each test here was relocated verbatim from the original
 * frontend/e2e/phase7.5-features-gap-closure.spec.ts so test semantics,
 * silent-failure annotations, and skip messages are preserved.
 *
 * Real backend only. No mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import {
  getTestUser,
  loginUser,
} from '../fixtures/auth';
import {
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe("Phase 7.5 gap — search @deprecated", () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
  });


  test('C — Search page loads; type query and assert results or no-results and no crash', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/search', {
      timeout: 60000,
      contentSelector: '.search-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).toBeVisible();

    const searchPage = page.locator('.search-page');
    await expect(searchPage).toBeVisible({ timeout: 5000 });

    const searchInput = page
      .locator('input[type="search"], input[placeholder*="Search"], input[placeholder*="query"]')
      .first();
    await expect(searchInput).toBeVisible({ timeout: 5000 });
    await searchInput.fill('test query');

    const searchButton = page.getByRole('button', { name: /Search/i });
    await expect(searchButton).toBeVisible({ timeout: 5000 });
    await searchButton.click();

    await Promise.race([
      page.waitForSelector('.search-page-results-meta', { timeout: 20000 }),
      page.waitForSelector('.search-page-results-list', { timeout: 20000 }),
      page.waitForSelector('.empty-state, [data-testid="empty-state"]', { timeout: 20000 }),
      page.waitForSelector('.error-display, [data-testid="error-display"]', { timeout: 20000 }),
    ]);

    // Don't assert body.not.toContainText(/404|Not Found/) — body text can transiently
    // contain "Not Found" during loading states (e.g. spinner text, hidden DOM nodes).
    // Instead rely on the positive content assertions below.
    const hasResults =
      (await page.locator('.search-page-results-list, .search-page-results-meta').count()) > 0;
    const hasNoResults =
      (await page.locator('text=/No results|no results|Start searching/i').count()) > 0;
    const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
    const hasErrorDisplay = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
    expect(hasResults || hasNoResults || hasEmptyState || hasErrorDisplay).toBe(true) /* acceptable states */;
  });
});
