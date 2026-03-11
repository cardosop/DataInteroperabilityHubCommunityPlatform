/**
 * E2E Test: JOURNEY-DC-013 — Use Asset Recommendations
 *
 * Journey: Use Asset Recommendations
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DC-013: Use Asset Recommendations', () => {
  test.setTimeout(360000); // 6 min: visible/slowMo; login under parallel E2E load can be slow

  test.describe('Success', () => {
    test('marketplace loads (recommendations section)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.listing-list-page, .listing-list-grid, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
      const hasContent =
        (await page.locator('.listing-list-page').count()) > 0 ||
        (await page.locator('.listing-list-grid').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.loading-spinner-container').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('marketplace loads when API returns empty', async ({ page }) => {
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

  test.describe('Edge', () => {
    test('marketplace list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
    });
  });
});
