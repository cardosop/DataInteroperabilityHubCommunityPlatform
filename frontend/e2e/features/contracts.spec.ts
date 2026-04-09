/**
 * E2E Feature: Contracts
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads, waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Contracts', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      await page.goto('/contracts');
      await page.waitForLoadState('domcontentloaded');
      await assertListPageLoads(page, '[data-testid="contract-list-page"], .contract-list-page, .empty-state', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/contracts/${nonExistentId}/edit`);
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch {
        // May resolve to error/login — acceptable
      }
      const onLogin = page.url().includes('/login');
      const hasError = (await page.locator('.error-display').count()) > 0;
      expect(onLogin || hasError).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('contract link-odps with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch {
        // May resolve to error/login/403 — acceptable
      }
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403|forbidden/i').count()) > 0;
      expect(hasError || onLogin || on403).toBe(true) /* acceptable states */;
    });
  });
});
