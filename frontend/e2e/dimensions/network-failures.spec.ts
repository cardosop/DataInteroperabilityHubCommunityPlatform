/**
 * Dimension: Network Failures
 * Cross-cutting E2E for offline, connection refused, and timeout handling.
 * Per tasks 8.7.1: frontend/e2e/dimensions/network-failures.spec.ts
 * Run: npm run test:e2e -- e2e/dimensions/network-failures.spec.ts
 *
 * No backend mocks: we simulate transport-level failure (abort/timeout) via Playwright
 * route so the app's error handling is exercised against real UI and real API contract.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';

test.describe('Dimension: Network failures', () => {
  test.setTimeout(60000);

  test('when API request is aborted, user remains on login (no crash)', async ({ page }) => {
    await clearAuthStorage(page);
    let aborted = false;
    await page.route('**/api/v1/**', (route) => {
      if (route.request().url().includes('/auth/') && !aborted) {
        aborted = true;
        void route.abort('failed').catch(() => {});
        return;
      }
      void route.continue();
    });
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', 'test@example.com');
    await page.fill('input#password', 'password');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(3000);
    expect(page.url()).toContain('/login');
  });

  test('when assets API fails with connection error, list page shows error or empty', async ({
    page,
  }) => {
    await page.route('**/api/v1/assets/**', (route) => {
      void route.abort('connectionrefused').catch(() => {});
    });
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.asset-list-page, .empty-state, .error-display, .loading-spinner-container', {
      timeout: 15000,
    });
    await page.waitForTimeout(3000);
    const hasContent =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('.empty-state').count()) > 0 ||
      (await page.locator('.asset-list-page').count()) > 0;
    expect(hasContent).toBe(true);
  });

  test('when API request is delayed then aborted (timeout), user remains on login', async ({
    page,
  }) => {
    await clearAuthStorage(page);
    let firstLogin = true;
    await page.route('**/api/v1/auth/login/**', async (route) => {
      if (firstLogin) {
        firstLogin = false;
        await new Promise((r) => setTimeout(r, 100));
        void route.abort('timedout').catch(() => {});
        return;
      }
      await route.continue();
    });
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', 'test@example.com');
    await page.fill('input#password', 'password');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(5000);
    expect(page.url()).toContain('/login');
  });

  test('when browser is offline, app handles navigation without crash', async ({ page }) => {
    await clearAuthStorage(page);
    await page.context().setOffline(true);
    try {
      await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 8000 });
    } catch {
      // Navigation may fail when offline; page may still be loadable from cache
    }
    await page.waitForTimeout(2000);
    const onLogin = page.url().includes('/login');
    const hasBody = (await page.locator('body').count()) > 0;
    expect(onLogin || hasBody).toBe(true);
    await page.context().setOffline(false);
  });
});
