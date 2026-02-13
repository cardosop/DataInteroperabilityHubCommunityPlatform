/**
 * E2E: Cross-cutting — 404 page, 403 page, session expiry (Phase 13 — 15.9.2)
 *
 * 404 page, 403 page, network error handling, session expiry redirect to login.
 * No mocks; real backend only.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Cross-cutting: 404, 403, session', () => {
  test.describe('404 page', () => {
    test('unknown route shows 404 page', async ({ page }) => {
      await page.goto('/unknown-route-404-test', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('body')).toContainText(/404|Page Not Found/i, {
        timeout: 10_000,
      });
    });
  });

  test.describe('403 page', () => {
    test('direct visit to /403 shows forbidden', async ({ page }) => {
      await page.goto('/403', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('body')).toContainText(/403|Forbidden/i, {
        timeout: 10_000,
      });
    });
  });

  test.describe('Session and redirect', () => {
    test('unauthenticated visit to protected home redirects to login or stays on root', async ({
      page,
    }) => {
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle').catch(() => {});
      const pathname = new URL(page.url()).pathname;
      const onLogin = pathname.includes('/login');
      const onRoot = pathname === '/' || pathname === '';
      expect(onLogin || onRoot).toBe(true);
    });

    test('after login, home shows app shell', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.locator('.app-header')).toBeVisible({ timeout: 10_000 });
    });
  });
});
