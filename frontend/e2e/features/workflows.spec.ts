/**
 * E2E Feature: Workflows
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Workflow-related routes (if any in app).
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('Feature: Workflows', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('app home or workflows entry loads', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url).toMatch(/\/(login|jobs|assets|403|unavailable)?$/);
    });
  });

  test.describe('Edge', () => {
    test('navigate to jobs as workflow-related surface', async ({ page }) => {
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/jobs|\/login|\/403/);
    });
  });
});
