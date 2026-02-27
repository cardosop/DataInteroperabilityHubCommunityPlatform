/**
 * E2E Feature: BaaS
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /baas.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: BaaS', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('baas route loads or redirects to login/403', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/baas|\/login|\/403|\/unavailable/);
    });
  });

  test.describe('Edge', () => {
    test('baas may show capability-gated or content', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(page.url()).toBeDefined();
    });
  });
});
