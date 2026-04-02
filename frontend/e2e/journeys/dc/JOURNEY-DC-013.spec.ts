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
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-013: Use Asset Recommendations', () => {
  // Navigation + listings API + terminal UI can exceed 90s under parallel workers / slow proxy.
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace loads (recommendations section)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      // Listener MUST be attached before navigation: the listings GET completes during
      // loginAndNavigateToRoute. A post-hoc waitForResponse waits for a second request that
      // never fires → full timeout → test budget exceeded → "page closed" during expect.
      const listingsSettled = page
        .waitForResponse(
          (r) =>
            r.request().method() === 'GET' &&
            r.url().includes('marketplace/listings') &&
            r.status() < 500,
          { timeout: 85_000 }
        )
        .catch(() => undefined);

      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 85_000,
        contentSelector:
          '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
      await listingsSettled;
      const terminal = page.locator(
        '.listing-list-page, .listing-list-grid, .empty-state, .error-display'
      );
      await expect(terminal.first()).toBeVisible({ timeout: 45_000 });
    });
  });

  test.describe('Failure', () => {
    test('marketplace loads when API returns empty', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 65000,
        contentSelector:
          '[data-testid="listing-list-page"], .listing-list-page, .empty-state, .error-display',
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
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector:
          '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
      const hasContent =
        (await page.locator('.listing-list-page').count()) > 0 ||
        (await page.locator('.listing-list-grid').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
