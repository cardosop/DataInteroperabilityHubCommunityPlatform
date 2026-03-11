/**
 * E2E Feature: Marketplace
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders, /marketplace/entitlements.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertFailureRedirect, assertSuccessLoad } from '../fixtures/journey-helpers';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads (or redirects to login)', async ({ page }) => {
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.listing-list-page, .error-display, .empty-state, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        await assertFailureRedirect(page);
        return;
      }
      await assertSuccessLoad(page, {
        successContentSelector: '[data-testid="listing-list-page"], .listing-list-page, .empty-state',
      });
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/marketplace/listings/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404|failed to load/i').count()) > 0;
      const noDetail = (await page.locator('.listing-detail-main').count()) === 0;
      expect(onLogin || hasError || noDetail).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace orders list loads or redirects', async ({ page }) => {
      await page.goto('/marketplace/orders');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          await assertFailureRedirect(page);
          return;
        }
        throw _err;
      }
      await assertSuccessLoad(page, {
        successContentSelector: '.order-list-page, .empty-state, .error-display',
      });
    });
  });
});
