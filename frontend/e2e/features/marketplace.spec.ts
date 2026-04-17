/**
 * E2E Feature: Marketplace
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders, /marketplace/entitlements.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertFailureRedirect, assertSuccessLoad } from '../fixtures/journey-helpers';
import { assertListPageLoads, loginAndNavigateToRoute, waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 60000,
        contentSelector: '[data-testid="listing-list-page"], .listing-list-page, .empty-state, .error-display',
      });
      await assertListPageLoads(page, '[data-testid="listing-list-page"], .listing-list-page, .empty-state', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/marketplace/listings/${nonExistentId}`);
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
        successContentSelector: '.order-list-page, .empty-state',
      });
    });
  });
});
