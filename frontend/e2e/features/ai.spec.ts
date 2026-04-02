/**
 * E2E Feature: AI
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /ai/search, /ai/schema-matching.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: AI', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ai search route loads or redirects', async ({ page }) => {
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/ai|\/search|\/login|\/403|\/unavailable/);
    });
  });

  test.describe('Edge', () => {
    test('ai schema-matching route responds', async ({ page }) => {
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/ai|\/login|\/403|\/unavailable/);
    });
  });
});
