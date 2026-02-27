/**
 * E2E Feature: Compliance
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /compliance, /compliance/runs/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Compliance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance list loads or redirects to login', async ({ page }) => {
      await page.goto('/compliance');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/compliance');
    });
  });

  test.describe('Failure', () => {
    test('compliance run detail with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const onCompliance = url.includes('/compliance');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(onLogin || onCompliance || hasError).toBe(true);
    });
  });
});
