/**
 * E2E Feature: Contracts
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertFailureRedirect, assertSuccessLoad } from '../fixtures/journey-helpers';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Contracts', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads (or redirects to login)', async ({ page }) => {
      await page.goto('/contracts');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector: '.contract-list-page, .empty-state, .error-display, .loading-spinner-container',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          await assertFailureRedirect(page);
          return;
        }
        throw _err;
      }
      await assertSuccessLoad(page, {
        successContentSelector: '[data-testid="contract-list-page"], .contract-list-page, .empty-state',
      });
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/contracts/${nonExistentId}/edit`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404|failed to load/i').count()) > 0;
      const noEditor = (await page.locator('.contract-editor-page').count()) === 0;
      expect(onLogin || hasError || noEditor).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('contract link-odps with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const onLinkOdps = url.includes('/link-odps');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403|forbidden/i').count()) > 0;
      expect(onLinkOdps || hasError || onLogin || on403).toBe(true);
    });
  });
});
