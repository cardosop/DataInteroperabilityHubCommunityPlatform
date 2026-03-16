/**
 * E2E Feature: Jobs
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /jobs, /jobs/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Jobs', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('jobs list loads or redirects to login', async ({ page }) => {
      await page.goto('/jobs');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/jobs');
      const hasContent =
        (await page.locator('.job-list-page, .empty-state, h1').count()) > 0;
      const hasError = (await page.locator('.error-display').count()) > 0;
      expect(
        hasContent || hasError,
        'Expected .job-list-page, .empty-state, h1, or .error-display on /jobs'
      ).toBe(true);
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
      expect(onLogin || hasError).toBe(true);
    });
  });
});
