/**
 * E2E Test: Login → Load App Shell
 *
 * DoD-2.2: Baseline smoke E2E exists for login → load app shell
 *
 * This test verifies the critical path:
 * 1. User can navigate to login page
 * 2. User can log in with credentials
 * 3. App Shell loads correctly (Header + Sidebar + Main content)
 * 4. Navigation works
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from './fixtures/auth';

test.describe('Login → Load App Shell (DoD-2.2)', () => {
  test.setTimeout(90000); // 90 seconds to handle rate limiting and slow API responses

  test('user can login and app shell loads correctly', async ({ page }) => {
    // Enable console logging for debugging
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.log(`Browser console error: ${msg.text()}`);
      }
    });

    // Step 1: Get test user (creates if needed)
    const testUser = await getTestUser();

    // Step 2: Use loginUser fixture (handles rate limiting, retries, and navigation)
    await loginUser(page, testUser);

    // Step 3: Wait for page to be fully loaded (after login)
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Wait for React to render

    // Step 5: Verify App Shell is loaded
    // Wait a bit for app to fully render
    await page.waitForTimeout(1000);

    // Verify Header is visible
    const header = page.locator('.app-header');
    await expect(header).toBeVisible({ timeout: 10000 });
    await expect(header.locator('.app-title')).toContainText('Data Interoperability Hub');

    // Verify global search is visible
    await expect(header.locator('.global-search')).toBeVisible();

    // Verify user menu is visible (user is logged in)
    await expect(header.locator('.user-menu')).toBeVisible({ timeout: 10000 });
    // User name is in user-menu-trigger, check that it exists
    const userMenuTrigger = header.locator('.user-menu-trigger');
    await expect(userMenuTrigger).toBeVisible({ timeout: 10000 });

    // Note: userMenuTrigger is reused below for opening the menu

    // Verify Sidebar is visible
    const sidebar = page.locator('.app-sidebar');
    await expect(sidebar).toBeVisible();
    await expect(sidebar.locator('.sidebar-nav')).toBeVisible();

    // Verify navigation items are present
    const navItems = sidebar.locator('.nav-link');
    await expect(navItems.first()).toBeVisible();
    const navCount = await navItems.count();
    expect(navCount).toBeGreaterThan(0);

    // Verify Main content area is visible
    const mainContent = page.locator('.app-main');
    await expect(mainContent).toBeVisible();

    // Step 6: Verify navigation works
    // Click on a navigation item (e.g., Home or first available)
    const homeLink = sidebar.locator('.nav-link').first();
    if ((await homeLink.count()) > 0) {
      await homeLink.click();
      // Wait for navigation
      await page.waitForTimeout(500);
      // Verify we're still in the app shell
      await expect(header).toBeVisible();
      await expect(sidebar).toBeVisible();
    }

    // Step 7: Verify tenant switcher is present (if user has tenant)
    const tenantSwitcher = header.locator('.tenant-switcher');
    if ((await tenantSwitcher.count()) > 0) {
      await expect(tenantSwitcher).toBeVisible();
    }

    // Step 8: Verify logout is accessible via user menu
    // Logout button is inside user-menu-dropdown, so we need to open the menu first
    // Open user menu to access logout button (userMenuTrigger already declared above)
    await userMenuTrigger.click();
    await page.waitForTimeout(500); // Wait for dropdown to appear

    // Verify logout button exists in dropdown
    const logoutMenuItem = header.locator('.user-menu-logout');
    await expect(logoutMenuItem).toBeVisible({ timeout: 5000 });
    await expect(logoutMenuItem).toContainText('Logout');
  });

  test('app shell persists across navigation', async ({ page }) => {
    test.setTimeout(60000); // 60 seconds

    // Login first
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    // Wait for app shell to be fully loaded
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Wait for React to render
    await expect(page.locator('.app-header')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10000 });

    // Navigate to different routes using sidebar links (more realistic)
    const sidebar = page.locator('.app-sidebar');

    // Try to click on "Datasets" link if available
    const datasetsLink = sidebar.locator('.nav-link').filter({ hasText: 'Datasets' });
    const linkCount = await datasetsLink.count();

    if (linkCount > 0) {
      await datasetsLink.first().click();
      await page.waitForTimeout(1000); // Wait for navigation

      // Verify shell is still visible
      await expect(page.locator('.app-header')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-main')).toBeVisible({ timeout: 10000 });
    } else {
      // If datasets link not available, just verify shell is stable
      await page.waitForTimeout(2000);
      await expect(page.locator('.app-header')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10000 });
    }
  });

  test('unauthenticated user is redirected to login', async ({ page }) => {
    test.setTimeout(30000); // 30 seconds

    // Try to access protected route without login
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });

    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page.locator('h1')).toContainText('Data Interoperability Hub', { timeout: 10000 });
  });
});
