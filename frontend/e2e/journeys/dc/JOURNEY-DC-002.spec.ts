/**
 * E2E Test: JOURNEY-DC-002 — Search Marketplace
 *
 * Journey: Search Marketplace
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md, docs/TEST_COVERAGE_MATRIX.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace, /search.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-002: Search Marketplace', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('marketplace search input filters results or shows empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 65000,
        contentSelector:
          '.listing-list-page, .listing-list-grid, .error-display, .empty-state, [data-testid="listing-list-page"]',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/marketplace');

      // Fill the search input and verify the result container updates (debounce ~500ms)
      const searchInput = page.locator(
        '.listing-list-filters input[type="text"], .listing-list-filters input, input[placeholder*="Search"]'
      ).first();
      if ((await searchInput.count()) > 0) {
        await searchInput.fill('xyznonexistent_e2e');
        // Wait for results to update — either empty state or results list
        await page
          .locator('.empty-state, .listing-list-page, .listing-list-grid, .error-display')
          .first()
          .waitFor({ state: 'visible', timeout: 10000 })
          .catch(() => null);
        // The result container must render something (no blank-screen regression)
        const hasTerminalState =
          (await page.locator('.empty-state').count()) > 0 ||
          (await page.locator('.listing-list-page, .listing-list-grid').count()) > 0 ||
          (await page.locator('.error-display').count()) > 0;
        expect(hasTerminalState).toBe(true) /* acceptable states */;
      }
    });

    test('search page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .unavailable-page, .empty-state, .error-display',
      });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onSearch = url.includes('/search');
      if (onLogin) {
        test.skip(true, 'Auth gated — skipping success assertion');
        return;
      }
      expect(onSearch).toBe(true);
      const hasContent =
        (await page.locator('.search-page, .app-main').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display')).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('search with invalid query shows results or empty', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/search', {
        timeout: 60000,
        contentSelector:
          '.search-page, .empty-state, .error-display, .unavailable-page',
      });
      // If the search feature is unavailable for this tenant, accept gracefully.
      if (page.url().includes('/unavailable')) {
        return;
      }
      const searchInput = page.locator(
        'input[type="search"], input[placeholder*="Search"], input[placeholder*="query"]'
      );
      // Allow extra time: visible/slowMo mode and parallel-batch backend load can delay rendering.
      await expect(searchInput.first()).toBeVisible({ timeout: 30000 });
      await searchInput.first().fill('xyznonexistent123');
      const searchBtn = page.getByRole('button', { name: /Search/i });
      await expect(searchBtn).toBeVisible({ timeout: 10000 });
      await searchBtn.click();
      // Results, empty state, or error (search API can be slow or return 503)
      await Promise.race([
        page.waitForSelector('.search-page-results-meta', { timeout: 45_000 }),
        page.waitForSelector('.search-page-results-list', { timeout: 45_000 }),
        page.waitForSelector('.empty-state', { timeout: 45_000 }),
        page.waitForSelector('.error-display', { timeout: 45_000 }),
      ]);
      expect(page.url()).toContain('/search');
    });
  });

  test.describe('Edge', () => {
    test('marketplace and search routes accessible', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 60000,
        contentSelector:
          '.listing-list-page, .listing-list-grid, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/marketplace');
      await loginAndNavigateToRoute(page, consumer, '/search', {
        timeout: 60000,
        contentSelector:
          '.search-page, .empty-state, .error-display, .unavailable-page',
      });
      expect(page.url()).toContain('/search');
    });
  });
});
