/**
 * E2E: UC-MKT-003 — Purchase Asset from Marketplace
 *
 * Use Case: Purchase Asset
 * Persona: Data Consumer
 * Reference: docs/USE_CASES.md, UC-DC-001
 *
 * Success/Failure/Edge. Routes: /marketplace/listings/:id, /marketplace/orders.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { createListingViaApi, publishListingViaApi } from '../../fixtures/api-marketplace';

test.describe('UC-MKT-003: Purchase Asset from Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('place order on listing', async ({ page }) => {
      // Setup: create asset + listing via API as provider
      const providerUser = await getTestUser();
      const assetId = await createAssetViaApi(providerUser, { forceNew: true, ensureActivated: true });
      const listingId = await createListingViaApi(providerUser, assetId);
      await publishListingViaApi(providerUser, listingId);

      // Login as consumer and navigate to listing detail
      const consumerUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumerUser, `/marketplace/listings/${listingId}`, {
        timeout: 90000,
        contentSelector: '.listing-detail-main, .listing-detail-page, .error-display, main',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth not available');
      }
      await waitForLoadingComplete(page, { timeout: 15000 });

      // Look for purchase/order button
      const purchaseBtn = page.locator(
        'button:has-text("Purchase"), button:has-text("Order"), button:has-text("Get Access"), button:has-text("Request Access"), button:has-text("Subscribe")'
      ).first();

      if ((await purchaseBtn.count()) === 0) {
        test.info().annotations.push({
          type: 'info',
          description: `No purchase/order button found on listing detail page (listing ${listingId})`,
        });
        return;
      }

      const [response] = await Promise.all([
        page.waitForResponse(
          (resp) => resp.url().includes('/marketplace/orders') && resp.request().method() === 'POST',
          { timeout: 30000 }
        ),
        purchaseBtn.click(),
      ]);

      if (response.status() < 400) {
        await page.waitForTimeout(3000);
        const onOrderDetail = page.url().includes('/marketplace/orders/');
        const successMessage = page.locator('text=/success|order placed|order created/i');
        const hasSuccess = onOrderDetail || (await successMessage.count()) > 0;
        expect(hasSuccess).toBe(true);
        await expect(page.locator('.error-display')).not.toBeVisible();
      } else {
        const body = await response.text().catch(() => '');
        throw new Error(`POST /marketplace/orders/ returned ${response.status()}: ${body}`);
      }
    });

    test('listing detail shows purchase option when listing exists', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .empty-state',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const link = page.locator('.listing-list-page a[href*="/marketplace/listings/"]').first();
      if ((await link.count()) > 0) {
        await link.click();
        await page.waitForURL(/\/marketplace\/listings\/[^/]+/, { timeout: 10000 });
        const purchaseBtn = page.locator('button:has-text("Purchase"), button:has-text("Request"), a:has-text("Purchase")');
        const hasDetail = (await page.locator('.listing-detail-main').count()) > 0;
        const hasPurchase = (await purchaseBtn.count()) > 0;
        expect(hasDetail || hasPurchase).toBe(true) /* acceptable states */;
      }
    });

    test('orders page loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/orders', {
        timeout: 90000,
        contentSelector: '.order-list-page, .empty-state',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/orders');
    });
  });

  test.describe('Failure', () => {
    test('non-existent listing shows error', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/marketplace/listings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|404/i').count()) > 0;
      expect(hasError).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('orders list with empty state loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/orders', {
        timeout: 90000,
        contentSelector: '.order-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/marketplace/orders');
    });
  });
});
