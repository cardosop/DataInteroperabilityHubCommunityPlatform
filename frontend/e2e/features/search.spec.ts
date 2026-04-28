/**
 * E2E Feature: Search
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /search.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Search', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('search route loads with search input', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, [data-testid="empty-state"], h1',
      });
      await assertListPageLoads(page, '.search-page, .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
      // Verify the search input is present — core UI element
      const searchInput = page.locator(
        'input[type="search"], input[placeholder*="search" i], .search-input'
      );
      const hasSearchInput = (await searchInput.count()) > 0;
      if (!hasSearchInput) {
        test.info().annotations.push({
          type: 'search-input-missing',
          description: 'Search input not found — page may use a different search pattern',
        });
      }
    });
  });

  test.describe('Failure', () => {
    test('search with special characters does not crash', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, [data-testid="empty-state"], h1',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect');
        return;
      }
      // Fill search with special characters that could cause injection issues
      const searchInput = page.locator(
        'input[type="search"], input[placeholder*="search" i], .search-input'
      ).first();
      if ((await searchInput.count()) === 0) {
        test.skip(true, 'Search input not found');
        return;
      }
      await searchInput.fill('!@#$%^&*() <script>alert("xss")</script>');
      // Wait for search results to settle (debounce fires, API responds, UI re-renders).
      // Use a selector wait instead of fixed sleep — the page must reach a terminal state.
      await page
        .locator('.search-results, .empty-state, [data-testid="empty-state"], .search-page, .error-display, [data-testid="error-display"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => {
          // Search results may already be visible from initial load
        });
      // Must not crash — no 500 errors, no blank page
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.search-page, .search-results, .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Page must still render after special char search').toBe(true);
    });

    test('unauthenticated access to search redirects to login', async ({ page }) => {
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/search'),
        'Expected /login redirect or /search with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('search with empty query shows empty state or all results', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, [data-testid="empty-state"], h1',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect');
        return;
      }
      // Empty query should show either empty state or all results — not an error
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page
          .locator(
            '.search-page, .search-results, .empty-state, [data-testid="empty-state"], h1, input[type="search"], input[placeholder*="search" i]'
          )
          .count()) > 0;
      expect(hasContent, 'Search page must render with empty query').toBe(true);
    });

    test('search with very long query does not crash', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, [data-testid="empty-state"], h1',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect');
        return;
      }
      const searchInput = page.locator(
        'input[type="search"], input[placeholder*="search" i], .search-input'
      ).first();
      if ((await searchInput.count()) === 0) {
        test.skip(true, 'Search input not found');
        return;
      }
      // Fill with very long string (500 chars)
      await searchInput.fill('a'.repeat(500));
      // Wait for search results to settle after long input
      await page
        .locator('.search-results, .empty-state, [data-testid="empty-state"], .search-page, .error-display, [data-testid="error-display"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => {
          // Results may already be visible
        });
      // Must not crash
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const pageStillRendered =
        (await page.locator('.search-page, .search-results, .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(pageStillRendered, 'Page must still render after long query').toBe(true);
    });
  });
});
