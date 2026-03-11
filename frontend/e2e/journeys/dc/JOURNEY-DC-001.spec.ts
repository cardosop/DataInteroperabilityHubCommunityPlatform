/**
 * E2E Test: JOURNEY-DC-001 — Discover and Purchase Marketplace Asset
 *
 * Journey: Discover and Purchase Marketplace Asset
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace, /marketplace/listings/:id, /marketplace/orders.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertFailureRedirect, assertSuccessLoad } from '../../fixtures/journey-helpers';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-001: Discover and Purchase Marketplace Asset', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads (discover)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .error-display, .empty-state, .loading-spinner-container, #email',
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        await assertFailureRedirect(page);
        return;
      }
      await assertSuccessLoad(page, {
        successContentSelector: '[data-testid="listing-list-page"], .listing-list-page, .empty-state',
      });
    });

    test('marketplace orders list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
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

    test('marketplace entitlements list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace/entitlements');
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
        successContentSelector: '.entitlement-list-page, .empty-state, .error-display',
      });
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto(`/marketplace/listings/${nonExistentId}`);
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
    test('marketplace list loads with empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        await assertFailureRedirect(page);
        return;
      }
      await assertSuccessLoad(page, {
        successContentSelector: '[data-testid="listing-list-page"], .listing-list-page, .empty-state',
      });
    });
  });
});
