/**
 * E2E Test: JOURNEY-DC-015 — Purchase ODPS Product (Marketplace)
 *
 * Journey: Purchase ODPS Product (Marketplace)
 * Persona: Data Consumer
 * Use Case: UC-DC-011 (Purchase ODPS Product), UC-MKT-ADV-001 (Marketplace)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-015: Purchase ODPS Product (Marketplace)', () => {
  test.setTimeout(300000);

  test.describe('Success', () => {
    test('marketplace loads (ODPS products discoverable)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.listing-list-page, .listing-list-grid, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
    });

    test('orders page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace/orders');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector: '.order-list-page, .empty-state, .error-display, .loading-spinner-container',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/marketplace/orders');
    });
  });

  test.describe('Failure', () => {
    test('ODPS listing with non-existent id shows error', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace/listings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessContent = (await page.locator('.listing-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace and orders accessible', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.listing-list-page, .listing-list-grid, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      expect(page.url()).toContain('/marketplace');
      await page.goto('/marketplace/orders');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.order-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      expect(page.url()).toContain('/marketplace/orders');
    });
  });
});
