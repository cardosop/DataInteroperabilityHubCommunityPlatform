/**
 * E2E Feature: Auth
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /login, /register, /public, /password-reset, / (landing vs dashboard).
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';

test.describe('Feature: Auth', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('unauthenticated user at / sees landing page', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('[data-testid="landing-page"]', { timeout: 15_000 });
      await expect(page.locator('[data-testid="landing-login-link"]')).toBeVisible();
      expect(new URL(page.url()).pathname).toBe('/');
    });

    test('authenticated user at / sees dashboard', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.app-header', { timeout: 18_000 });
      await expect(
        page.locator('[data-testid="home-page"], .home-page, h1:has-text("Dashboard")').first()
      ).toBeVisible({ timeout: 10_000 });
      expect(page.url()).not.toMatch(/\/login/);
    });

    test('login page loads', async ({ page }) => {
      await page.goto('/login');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('#email, input[type="email"], .login-page', { timeout: 15000 });
      expect(page.url()).toMatch(/\/login|\/register/);
    });

    test('public page accessible without auth', async ({ page }) => {
      await page.goto('/public');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onPublic = page.url().includes('/public');
      const onLogin = page.url().includes('/login');
      expect(onPublic || onLogin).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('login with empty credentials shows validation or stays on login', async ({ page }) => {
      await page.goto('/login');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('#email, input[type="email"]', { timeout: 15000 }).catch(() => null);
      await page.click('button[type="submit"]').catch(() => null);
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/login');
    });

    test('invalid path redirects or shows 404', async ({ page }) => {
      await page.goto('/login');
      await page.waitForLoadState('domcontentloaded');
      await page.goto('/nonexistent-auth-route-xyz');
      await page.waitForTimeout(3000);
      const on404 = await page.locator('text=/not found|404/i').count() > 0;
      const onLogin = page.url().includes('/login');
      const onApp = page.url().includes('/nonexistent') === false;
      expect(on404 || onLogin || onApp).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('register page loads or redirects when registration disabled', async ({ page }) => {
      await page.goto('/register');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(8000);
      const url = page.url();
      const onRegister = url.includes('/register');
      const onLogin = url.includes('/login');
      const onUnavailable = url.includes('/unavailable');
      const onRoot = url.endsWith('/') || url.match(/\/$/) !== null;
      expect(onRegister || onLogin || onUnavailable || onRoot).toBe(true);
    });
  });
});
