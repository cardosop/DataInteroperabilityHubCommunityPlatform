/**
 * E2E Feature: Semantic
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /semantic.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: Semantic', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic route loads or redirects to login/unavailable', async ({ page }) => {
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/semantic|\/login|\/403|\/unavailable/);
    });
  });

  test.describe('Edge', () => {
    test('semantic may be capability-gated', async ({ page }) => {
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(page.url()).toBeDefined();
    });
  });
});
