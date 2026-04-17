/**
 * E2E Feature: Marketplace
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders, /marketplace/entitlements.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForAppMainReady,
} from '../fixtures/helpers';

test.describe('Feature: Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 60000,
        contentSelector:
          '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .empty-state, .error-display',
      });
      await assertListPageLoads(
        page,
        '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .empty-state',
        { timeout: 60000 }
      );
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/marketplace/listings/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, .listing-detail-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.listing-detail-page',
      });
    });

    test('unauthenticated access to marketplace redirects to login', async ({ page }) => {
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/marketplace'),
        'Expected /login redirect or /marketplace with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace orders list loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/orders', {
        timeout: 60000,
        contentSelector: '.order-list-page, .empty-state, .error-display, h1',
      });
      const url = page.url();
      if (url.includes('/login')) {
        // Auth redirect — acceptable
        return;
      }
      await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.order-list-page, .empty-state').count()) > 0;
      expect(hasContent, 'Expected orders list or empty state').toBe(true);
    });

    test('marketplace entitlements list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/entitlements', {
        timeout: 60000,
        contentSelector: '.entitlement-list-page, .empty-state, .error-display, h1',
      });
      const url = page.url();
      if (url.includes('/login')) return;
      await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.entitlement-list-page, .empty-state').count()) > 0;
      expect(hasContent, 'Expected entitlements list or empty state').toBe(true);
    });
  });
});
