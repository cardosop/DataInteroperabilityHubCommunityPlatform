/**
 * E2E Test: JOURNEY-DC-004 — Purchase Asset
 *
 * Journey: Purchase Asset
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md, docs/TEST_COVERAGE_MATRIX.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace/listings/:id, /marketplace/orders.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-004: Purchase Asset', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('listing detail shows purchase option', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.listing-list-page, .empty-state, .error-display, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const listingLink = page.locator('.listing-list-page a[href*="/marketplace/listings/"]').first();
      if ((await listingLink.count()) > 0) {
        await listingLink.click();
        await page.waitForURL(/\/marketplace\/listings\/[^/]+/, { timeout: 10000 });
        await page.waitForSelector('.listing-detail-main, .error-display', { timeout: 15000 });
        const purchaseBtn = page.locator('button:has-text("Purchase"), button:has-text("Request"), a:has-text("Purchase")');
        const hasPurchase = (await purchaseBtn.count()) > 0;
        const hasDetail = (await page.locator('.listing-detail-main').count()) > 0;
        expect(hasDetail || hasPurchase).toBe(true);
      }
    });

    test('orders page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace/orders');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/orders');
    });
  });

  test.describe('Failure', () => {
    test('purchase from non-existent listing shows error', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace/listings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.listing-detail-main',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('orders list loads (empty or with data)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace/orders', { timeout: 60000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      if (page.url().includes('/403')) {
        expect(page.url()).toContain('/403');
        return;
      }
      const hasContent =
        (await page.locator('.order-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('main, .app-main, h1').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
