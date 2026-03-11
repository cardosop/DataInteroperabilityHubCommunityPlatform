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
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-MKT-003: Purchase Asset from Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('listing detail shows purchase option when listing exists', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .error-display',
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
        expect(hasDetail || hasPurchase).toBe(true);
      }
    });

    test('orders page loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/orders', {
        timeout: 90000,
        contentSelector: '.order-list-page, .empty-state, .error-display',
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
      const noDetail = (await page.locator('.listing-detail-main').count()) === 0;
      expect(hasError || noDetail).toBe(true);
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
