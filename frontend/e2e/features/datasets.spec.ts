/**
 * E2E Feature: Datasets
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /datasets, /datasets/create, /datasets/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Datasets', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('datasets list loads or redirects to login', async ({ page }) => {
      await page.goto('/datasets');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/datasets');
    });
  });

  test.describe('Failure', () => {
    test('dataset detail with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/datasets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(onLogin || hasError).toBe(true);
    });
  });
});
