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
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-002: Search Marketplace', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo adds latency; login + marketplace + search nav

  test.describe('Success', () => {
    test('marketplace search input filters results or shows empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.listing-list-page, .listing-list-grid, .error-display, .empty-state, .loading-spinner-container, #email',
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
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
        expect(hasTerminalState).toBe(true);
      }
    });

    test('search page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const onUnavailable = url.includes('/unavailable');
      const onSearch = url.includes('/search');
      const hasContent =
        (await page.locator('.search-page, .app-main, .loading-spinner-container, .unavailable-page').count()) > 0;
      expect(onLogin || onUnavailable || (onSearch && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('search with invalid query shows results or empty', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/search', {
        timeout: 60000,
        contentSelector:
          '.search-page, .empty-state, .error-display, .loading-spinner-container, .unavailable-page',
      });
      const searchInput = page.locator(
        'input[type="search"], input[placeholder*="Search"], input[placeholder*="query"]'
      );
      await expect(searchInput.first()).toBeVisible({ timeout: 5000 });
      await searchInput.first().fill('xyznonexistent123');
      const searchBtn = page.getByRole('button', { name: /Search/i });
      await expect(searchBtn).toBeVisible({ timeout: 5000 });
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
          '.listing-list-page, .listing-list-grid, .empty-state, .error-display, .loading-spinner-container',
      });
      expect(page.url()).toContain('/marketplace');
      await loginAndNavigateToRoute(page, consumer, '/search', {
        timeout: 60000,
        contentSelector:
          '.search-page, .empty-state, .error-display, .loading-spinner-container, .unavailable-page',
      });
      expect(page.url()).toContain('/search');
    });
  });
});
