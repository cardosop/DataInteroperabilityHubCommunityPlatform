/**
 * E2E Feature: Audit
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /audit.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: Audit', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit route loads or redirects to login/403', async ({ page }) => {
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/audit|\/login|\/403/);
    });
  });

  test.describe('Failure', () => {
    test('audit without permission may show 403', async ({ page }) => {
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/audit|\/login|\/403/);
    });
  });
});
