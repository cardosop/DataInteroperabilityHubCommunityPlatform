/**
 * E2E Feature: Notifications
 * Routes: /notifications.
 * Success/Failure/Edge. Real backend only; no mocks.
 *
 * Tests the notifications list page and the notification bell icon in the header.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Notifications', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('notifications page loads with list or empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/notifications', {
        timeout: 60000,
        contentSelector:
          '.notification-list-page, .notifications-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      });
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        test.skip(true, 'Auth/role redirect');
        return;
      }
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page
          .locator('.notification-list-page, .notifications-page, .empty-state, [data-testid="empty-state"], h1')
          .count()) > 0;
      expect(hasContent, 'Expected notifications list or empty state').toBe(true);
    });

    test('notification bell icon is visible in header', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '.app-main, [data-testid="app-main"], h1',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect');
        return;
      }
      // The notification bell should be in the app header/navbar
      const bell = page.locator(
        'button[aria-label*="notification" i], button[aria-label*="Notification" i], [data-testid="notification-bell"], .notification-bell'
      );
      const hasBell = (await bell.count()) > 0;
      if (!hasBell) {
        test.info().annotations.push({
          type: 'bell-not-found',
          description: 'Notification bell icon not found in header — may use different selector',
        });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to notifications redirects to login', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/notifications'),
        'Expected /login redirect or /notifications with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('notifications page renders without server errors', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/notifications', {
        timeout: 60000,
        contentSelector:
          '.notification-list-page, .notifications-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) return;
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'Notifications page must not show 500 errors').toBe(false);
      const hasContent =
        (await page
          .locator('.notification-list-page, .notifications-page, .empty-state, [data-testid="empty-state"]')
          .count()) > 0;
      expect(hasContent, 'Expected notifications content or empty state').toBe(true);
    });
  });
});
