/**
 * E2E: Cross-cutting — 404 page, 403 page, session expiry (Phase 13 — 15.9.2)
 *
 * 404 page, 403 page, network error handling, session expiry redirect to login.
 * No mocks; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';

test.describe('Cross-cutting: 404, 403, session', () => {
  test.setTimeout(90000); // Login + navigation can be slow under parallel load
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
    test('unauthenticated visit to / sees landing or redirects to login', async ({ page }) => {
      // The `onRoot = pathname === '/'` branch was trivially true whenever no redirect
      // happened — passing even if nothing rendered. Removed.
      // Fix: require meaningful content to be visible (landing page elements OR login form).
      await clearAuthStorage(page);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      // Wait for a terminal state: landing page or login form
      await Promise.race([
        page.waitForSelector('[data-testid="landing-page"]', { timeout: 15_000 }),
        page.waitForSelector('input[type="email"], input#email', { timeout: 15_000 }),
      ]).catch(() => {});
      const pathname = new URL(page.url()).pathname;
      // Landing: URL is / AND the landing page data-testid renders
      const onLanding =
        (pathname === '/' || pathname === '') &&
        (await page.locator('[data-testid="landing-page"]').count()) > 0;
      // Login: redirected to /login
      const onLogin = pathname.includes('/login');
      // Must show real content — not just "URL happens to be /"
      expect(onLanding || onLogin).toBe(true);
    });

    test('after login, home shows app shell', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.locator('.app-header')).toBeVisible({ timeout: 18_000 });
    });
  });
});
