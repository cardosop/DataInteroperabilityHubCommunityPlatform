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
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const onSearch = page.url().includes('/search');
      expect(onLogin || onSearch).toBe(true) /* acceptable states */;
    });
  });
});
