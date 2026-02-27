/**
 * E2E Feature: Data Quality
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /dq, /dq/runs/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Data Quality', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('DQ list loads or redirects to login', async ({ page }) => {
      await page.goto('/dq');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/dq');
    });
  });

  test.describe('Failure', () => {
    test('DQ run detail with non-existent id shows error', async ({ page }) => {
      await page.goto('/dq/runs/00000000-0000-0000-0000-000000000000');
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
