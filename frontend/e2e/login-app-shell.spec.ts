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
import { clearAuthStorage, getTestUser, loginUser } from './fixtures/auth';
import { E2E_APP_NAME } from './fixtures/brand';
import { isBenignConsoleError } from './fixtures/console-utils';
import { waitForLoadingComplete } from './fixtures/helpers';
import { verifyViaApi } from './fixtures/verifyViaApi';

test.describe('Login → Load App Shell (DoD-2.2)', () => {
  test.setTimeout(120000);

  test('user can login and app shell loads correctly', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!isBenignConsoleError(text)) {
          console.log(`Browser console error: ${text}`);
        }
      }
    });

    // Step 1: Get test user (creates if needed)
    const testUser = await getTestUser();

    // Step 2: Use loginUser fixture (handles rate limiting, retries, and navigation)
    await loginUser(page, testUser);

    // If loginUser returned but the page is on /login (auth state destabilized
    // after the stability check passed — e.g. async tryFetchUser returned 401),
    // retry once with force-fresh login.
    if (page.url().includes('/login')) {
      await loginUser(page, testUser, { forceFreshLogin: true });
    }

    // Dual-channel login verification (PR 7a-ext2c — fourth adoption).
    // loginUser succeeded at the UI level (form submit + redirect), but
    // that only proves the client-side state transition. Hit /auth/me/
    // directly to confirm the session is real server-side — catches the
    // failure mode where the UI shows "logged in" but the token was
    // actually rejected (e.g. the stale-bearer-on-login bug fa87ce28
    // closed). Using a predicate that matches the expected email so a
    // wrong-user session (e.g. cached from a prior run) also surfaces.
    await verifyViaApi(
      page,
      '/api/v1/auth/me/',
      (body: { email?: string }) =>
        typeof body.email === 'string' &&
        body.email.toLowerCase() === testUser.email.toLowerCase(),
    );

    // Step 3: Wait for page to be fully loaded (after login)
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Wait for React to render
    await waitForLoadingComplete(page, { timeout: 15000 });

    // Step 5: Verify App Shell is loaded
    const header = page.locator('.app-header, [data-testid="app-header"]').first();
    await expect(header).toBeVisible({ timeout: 15000 });
    await expect(header.locator('.app-title')).toContainText(E2E_APP_NAME);

    // Verify global search is visible
    await expect(header.locator('.global-search')).toBeVisible();

    // Verify user menu is visible (user is logged in; may be .user-menu or .user-menu-trigger)
    const userMenu = header.locator('.user-menu, .user-menu-trigger');
    await expect(userMenu.first()).toBeVisible({ timeout: 15000 });
    // User name is in user-menu-trigger; use it for opening dropdown (trigger is inside .user-menu)
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
    const mainContent = page.locator('.app-main, [data-testid="app-main"]').first();
    await expect(mainContent).toBeVisible();

    // Step 6: Verify navigation works
    // Click on a navigation item (e.g., Home or first available)
    const homeLink = sidebar.locator('.nav-link').first();
    await expect(homeLink).toBeVisible({ timeout: 5000 });
    await homeLink.click();
    // Wait for navigation
    await page.waitForTimeout(500);
    // Verify we're still in the app shell
    await expect(header).toBeVisible();
    await expect(sidebar).toBeVisible();

    // Step 7: Verify tenant switcher is present (user always has a tenant after login)
    const tenantSwitcher = header.locator('.tenant-switcher');
    await expect(tenantSwitcher).toBeVisible({ timeout: 5000 });

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
    test.setTimeout(120000);

    // Login first
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    // Wait for app shell to be fully loaded
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Wait for React to render
    await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10000 });

    // Navigate to different routes using sidebar links.
    // Previously silently skipped to a weaker assertion when the Datasets link wasn't present.
    // Fix: use the first available nav link (always present after login) so navigation is
    // always exercised — then fall back to a known-stable route if no link renders.
    const sidebar = page.locator('.app-sidebar');
    const allNavLinks = sidebar.locator('.nav-link');
    const navLinkCount = await allNavLinks.count();

    if (navLinkCount > 0) {
      // Prefer Datasets; fall back to the first available nav link
      const datasetsLink = sidebar.locator('.nav-link').filter({ hasText: 'Datasets' });
      const linkToClick =
        (await datasetsLink.count()) > 0 ? datasetsLink.first() : allNavLinks.first();

      await linkToClick.click();
      await page.waitForTimeout(1000);

      // Navigation must have happened AND shell must still be visible
      await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible({ timeout: 10000 });
    } else {
      // No nav links rendered at all — navigate via URL to a known protected route
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);
      await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('unauthenticated user is redirected to login', async ({ page }) => {
    test.setTimeout(30000); // 30 seconds

    await clearAuthStorage(page);
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });

    await page.waitForURL(/\/login/, { timeout: 15000 });
    await expect(page.locator('h1')).toContainText(E2E_APP_NAME, { timeout: 10000 });
  });

  test('logout redirects to login and clears auth tokens', async ({ page }) => {
    test.setTimeout(120000);

    // Login first
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 15000 });

    // Confirm tokens are present before logout
    const tokenBefore = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(tokenBefore).toBeTruthy();

    // Open user menu and click logout
    const userMenuTrigger = page.locator('.user-menu-trigger');
    await userMenuTrigger.click();
    const logoutBtn = page.locator('.user-menu-logout');
    await expect(logoutBtn).toBeVisible({ timeout: 5000 });
    await logoutBtn.click();

    // After logout the app clears auth state. RootRoute behaviour depends on the current path:
    //   - At '/'  → isAuthenticated=false + isRoot=true → renders LandingPage (URL stays '/')
    //   - At any other path → Navigate to='/login'
    //
    // IMPORTANT: the URL never changes when logging out from '/', so waitForURL(/\/(login|$)/)
    // would resolve immediately on the current URL before clearAuth() has run. Instead we wait
    // directly on the observable side-effect we care about: localStorage.access_token becoming null.
    // authService.clearAuth() runs synchronously in the finally-block of authService.logout() so
    // this waitForFunction reliably signals that the full logout sequence has completed.
    await page.waitForFunction(
      () => localStorage.getItem('access_token') === null,
      { timeout: 15000 }
    );

    // Verify the page reflects the unauthenticated state (landing page or login page)
    const postLogoutUrl = page.url();
    const isOnLogin = postLogoutUrl.includes('/login');
    const isOnLanding =
      (new URL(postLogoutUrl).pathname === '/' || new URL(postLogoutUrl).pathname === '') &&
      (await page.locator('[data-testid="landing-page"], .landing-page, h1').count()) > 0;
    const appShellGone = (await page.locator('.app-header, [data-testid="app-header"]').first().count()) === 0;
    expect(isOnLogin || isOnLanding || appShellGone).toBe(true) /* acceptable states */;

    // Tokens must be cleared from localStorage (already confirmed by waitForFunction above,
    // but assert all three keys for completeness)
    const tokenAfter = await page.evaluate(() => ({
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token'),
      user: localStorage.getItem('user'),
    }));
    expect(tokenAfter.access).toBeNull();
    expect(tokenAfter.refresh).toBeNull();
    expect(tokenAfter.user).toBeNull();

    // Protected route should now redirect back to login (session is gone).
    // Wait for the SPA to settle after logout — calling page.goto immediately
    // can race with React re-render/state updates and abort the navigation.
    await page.waitForTimeout(1000);
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    await page.waitForURL(/\/login/, { timeout: 10000 });
  });
});
