/**
 * E2E Feature: Jobs
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /jobs, /jobs/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads } from '../fixtures/helpers';

test.describe('Feature: Jobs', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('jobs list loads', async ({ page }) => {
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await assertListPageLoads(page, '.job-list-page, .empty-state, h1', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      await page.goto('/jobs/00000000-0000-0000-0000-000000000000');
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
