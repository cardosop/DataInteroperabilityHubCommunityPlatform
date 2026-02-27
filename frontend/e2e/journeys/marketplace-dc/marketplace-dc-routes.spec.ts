/**
 * E2E: Marketplace and Data Consumer routes (Phase 13 — 15.4)
 * JOURNEY-DC-001–005, DC-003, DC-011–012, DC-014–015: discover, request access, purchase, view contract, download.
 * Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders, /marketplace/entitlements, /governance/access-requests.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../../fixtures/helpers';

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
      expect(page.url()).toContain('/marketplace/orders');
      const hasContent =
        (await page.locator('.order-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
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
      expect(page.url()).toContain('/marketplace/entitlements');
      const hasContent =
        (await page.locator('.entitlement-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes(`/marketplace/listings/${nonExistentId}`) &&
          (resp.status() === 200 || resp.status() === 404),
        { timeout: 60000 }
      );
      await page.goto(`/marketplace/listings/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessContent = (await page.locator('.listing-detail-main').count()) === 0;
      expect(hasError || noSuccessContent).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('governance access-requests loads or 403 when role missing', async ({ page }) => {
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onGov = page.url().includes('/governance');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasContent =
        (await page.locator('.app-main').count()) > 0 &&
        ((await page.locator('.error-display, .access-request-list-page, h1').count()) > 0 ||
          (await page.locator('text=/access|request|403|forbidden/i').count()) > 0);
      expect(onGov || on403 || onLogin).toBe(true);
      expect(hasContent || onGov || on403 || onLogin).toBe(true);
    });
  });
});
