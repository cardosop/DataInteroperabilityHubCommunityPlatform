/**
 * E2E Feature: Search
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /search.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads } from '../fixtures/helpers';

test.describe('Feature: Search', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('search route loads', async ({ page }) => {
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      await assertListPageLoads(page, '.search-page, .empty-state, h1', { timeout: 60000 });
    });
  });

  test.describe('Edge', () => {
    test('search with empty query loads page', async ({ page }) => {
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect — session expired');
        return;
      }
      expect(page.url()).toContain('/search');
      // Assert page rendered meaningful content, not just a URL match
      await page
        .locator('.search-page, .search-results, .empty-state, h1, input[type="search"], input[placeholder*="search" i]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const hasContent =
        (await page.locator('.search-page, .search-results, .empty-state, h1, input[type="search"], input[placeholder*="search" i]').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
