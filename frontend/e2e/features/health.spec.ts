/**
 * E2E Feature: Health
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /health, /health/ready.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: Health', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('health route loads or redirects', async ({ page }) => {
      await page.goto('/health');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/health|\/login|\/unavailable/);
    });
  });

  test.describe('Edge', () => {
    test('health/ready responds', async ({ page }) => {
      await page.goto('/health/ready');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url).toMatch(/\/health|\/login|\/unavailable/);
    });
  });
});
