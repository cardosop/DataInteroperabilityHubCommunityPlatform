/**
 * E2E Feature: Versioning
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Versioning routes (e.g. dataset versions).
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads } from '../fixtures/helpers';

test.describe('Feature: Versioning', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('datasets route with versions context loads', async ({ page }) => {
      await page.goto('/datasets');
      await page.waitForLoadState('domcontentloaded');
      await assertListPageLoads(page, '.dataset-list-page, .empty-state, h1', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('invalid dataset id for versions shows error or redirect', async ({ page }) => {
      await page.goto('/datasets/00000000-0000-0000-0000-000000000000/versions');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(onLogin || hasError).toBe(true) /* acceptable states */;
    });
  });
});
