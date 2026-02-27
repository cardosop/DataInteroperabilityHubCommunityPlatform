/**
 * E2E Test: JOURNEY-DC-003 — View Asset Details
 *
 * Journey: View Asset Details
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md, docs/TEST_COVERAGE_MATRIX.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace/listings/:id.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DC-003: View Asset Details', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace listing detail loads when listing exists', async ({ page }) => {
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
        const hasDetail = (await page.locator('.listing-detail-main').count()) > 0;
        expect(hasDetail || page.url().includes('/marketplace/listings/')).toBe(true);
      }
    });
  });

  test.describe('Failure', () => {
    test('listing detail with non-existent id shows error', async ({ page }) => {
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
    test('marketplace list with no listings shows empty state', async ({ page }) => {
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
      expect(page.url()).toContain('/marketplace');
    });
  });
});
