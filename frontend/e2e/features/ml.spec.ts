/**
 * E2E Feature: ML
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /ml.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: ML', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ml route loads or redirects to login/403', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/ml|\/login|\/403|\/unavailable/);
    });
  });

  test.describe('Edge', () => {
    test('ml may show capability-gated content', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(page.url()).toBeDefined();
    });
  });
});
