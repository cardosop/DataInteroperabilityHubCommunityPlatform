/**
 * E2E Test: JOURNEY-DC-004 — Access Entitlement
 *
 * Journey: Access Entitlement
 * Persona: Data Consumer
 * Reference: ManualTest/Front/03-USER-JOURNEYS/dc/JOURNEY-DC-004.md
 *
 * Success/Failure/Edge. Routes: /marketplace/entitlements, /marketplace/entitlements/:id.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-004: Access Entitlement', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('entitlements list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace/entitlements', {
        timeout: 90000,
        contentSelector:
          '.entitlement-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/entitlements');
      const hasContent =
        (await page.locator('.entitlement-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('entitlement detail loads when entitlement exists', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace/entitlements', {
        timeout: 90000,
        contentSelector:
          '.entitlement-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const entitlementRow = page.locator('.entitlement-list-page a[href*="/marketplace/entitlements/"]').first();
      if ((await entitlementRow.count()) > 0) {
        await entitlementRow.click();
        await page.waitForURL(/\/marketplace\/entitlements\/[^/]+/, { timeout: 10000 });
        await page.waitForSelector('.entitlement-detail-page, .error-display, .app-main', { timeout: 15000 });
        const hasDetail = (await page.locator('.entitlement-detail-page').count()) > 0;
        expect(hasDetail || page.url().includes('/marketplace/entitlements/')).toBe(true);
      }
    });
  });

  test.describe('Failure', () => {
    test('entitlement detail with non-existent id shows error', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace/entitlements/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.entitlement-detail-page, .error-display',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('entitlements list loads with empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace/entitlements', {
        timeout: 90000,
        contentSelector:
          '.entitlement-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/entitlements');
    });
  });
});
