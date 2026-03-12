/**
 * E2E: Marketplace and Data Consumer routes (Phase 13 — 15.4)
 * JOURNEY-DC-001–005, DC-003, DC-011–012, DC-014–015: discover, request access, purchase, view contract, download.
 * Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders, /marketplace/entitlements, /governance/access-requests.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('Marketplace and Data Consumer routes', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads (discover)', async ({ page }) => {
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.listing-list-page, .error-display, .empty-state, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
      // .listing-list-page must be visible; error-display is not an acceptable success outcome
      await assertListPageLoads(page, '.listing-list-page, .empty-state');
    });

    test('marketplace orders list loads', async ({ page }) => {
      await page.goto('/marketplace/orders');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/orders');
      // error-display must not be accepted as a success outcome for the orders list
      await assertListPageLoads(page, '.order-list-page, .empty-state');
    });

    test('marketplace entitlements list loads', async ({ page }) => {
      await page.goto('/marketplace/entitlements');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/entitlements');
      // error-display must not be accepted as a success outcome for the entitlements list
      await assertListPageLoads(page, '.entitlement-list-page, .empty-state');
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Added .catch(() => null) — without it, if a login redirect fires before the API
      // responds, the 15s waitForResponse hard-throws instead of gracefully handling it.
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes(`/marketplace/listings/${nonExistentId}`) &&
          resp.status() === 404,  // Only 404 is valid — 200 means the listing exists
        { timeout: 15000 }
      ).catch(() => null);
      await page.goto(`/marketplace/listings/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      // Race: wait for error or listing content rather than sleeping
      await page.locator('.error-display, .error-display-title, .listing-detail-main')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Marketplace listing shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace listing detail with missing required params shows error or redirect', async ({
      page,
    }) => {
      // Navigate to a listing URL with a well-formed but non-existent purchase flow path
      await page.goto('/marketplace/listings/00000000-0000-0000-0000-000000000000/purchase');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();

      // Redirect to login is always acceptable
      if (url.includes('/login')) return;

      // If still on the purchase path, the app must show an error boundary —
      // silently rendering a broken form is not acceptable
      const onPurchasePath = url.includes('/marketplace/listings/');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;

      if (onPurchasePath) {
        // Stayed on the purchase path — must show an error, not a working purchase form
        expect(hasError).toBe(true);
        return;
      }

      // Redirected to another marketplace route (e.g. back to listing list) — also acceptable
      expect(url).toContain('/marketplace');
    });
  });
});
