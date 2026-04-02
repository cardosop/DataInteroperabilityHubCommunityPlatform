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
      // RootRoute redirects unauthenticated users to /login after hydrate; URL can
      // still be /marketplace briefly — wait for login route or marketplace UI.
      await page.waitForFunction(
        () => {
          const path = window.location.pathname;
          if (path === '/login' || path.startsWith('/login/')) return true;
          return !!document.querySelector(
            '[data-testid="skeleton-row"], [data-testid="listing-list-page"], .listing-list-page, .empty-state, .error-display'
          );
        },
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        await assertFailureRedirect(page);
        return;
      }
      // ListingListPage shows ListPageSkeleton until the listings API returns
      await page.waitForSelector(
        [
          '[data-testid="listing-list-page"]',
          '.listing-list-page',
          '.empty-state',
          '.error-display',
          '[data-testid="skeleton-row"]',
        ].join(', '),
        { timeout: 65000 }
      );
      const skeleton = page.locator('[data-testid="skeleton-row"]');
      if (await skeleton.first().isVisible().catch(() => false)) {
        await page.waitForSelector(
          '[data-testid="listing-list-page"], .listing-list-page, .empty-state, .error-display',
          { timeout: 60000 }
        );
      }
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
