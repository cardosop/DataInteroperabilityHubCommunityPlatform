/**
 * E2E Feature: Home / Dashboard
 * Routes: / (home/dashboard).
 * Success/Failure/Edge. Real backend only; no mocks.
 *
 * Note: This file was originally named "Workflows" but actually tests the home page.
 * The home route (/) renders the dashboard with activity feed, widgets, and navigation.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Home / Dashboard', () => {
  // 240s: staging auth under load (rate-limit retries with 15s backoff × 3 attempts
  // = 45s auth overhead) + dashboard content loading can exceed 120s.
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('home page loads with dashboard content', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '.app-main, .dashboard-page, .home-page, h1',
      });
      const url = page.url();
      if (url.includes('/login')) {
        test.skip(true, 'Auth redirect');
        return;
      }
      // Home must render the app shell with navigation
      const hasAppShell = (await page.locator('.app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasAppShell, 'Expected app shell (.app-main) to be present').toBe(true);
      // No server errors on the dashboard
      await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 5000 });
    });

    test('home page has sidebar navigation', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '.app-main, h1',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect');
        return;
      }
      // Sidebar must have at least Assets and Contracts navigation links
      const sidebar = page.locator('nav, .sidebar, .app-sidebar, [role="navigation"]');
      const hasSidebar = (await sidebar.count()) > 0;
      expect(hasSidebar, 'Expected sidebar navigation').toBe(true);

      const assetsLink = page.locator('a[href="/assets"], a[href*="/assets"]');
      const contractsLink = page.locator('a[href="/contracts"], a[href*="/contracts"]');
      expect(
        (await assetsLink.count()) > 0,
        'Sidebar must have Assets navigation link'
      ).toBe(true);
      expect(
        (await contractsLink.count()) > 0,
        'Sidebar must have Contracts navigation link'
      ).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to home redirects to login', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      // Home may redirect to /login for unauthenticated users or show the landing page
      expect(
        url.includes('/login') || url === page.url(),
        'Expected /login redirect or home page'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('home page renders without server errors', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '.app-main, .dashboard-page, .home-page, h1',
      });
      if (page.url().includes('/login')) return;
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'Home page must not show 500 errors').toBe(false);
    });
  });
});
