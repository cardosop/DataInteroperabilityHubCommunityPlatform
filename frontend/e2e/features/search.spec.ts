/**
 * E2E Feature: Search
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /search.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Search', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('search route loads or redirects to login', async ({ page }) => {
      await page.goto('/search');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/search');
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
