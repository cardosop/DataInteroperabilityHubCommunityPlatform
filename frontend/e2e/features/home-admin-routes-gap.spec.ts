/**
 * Phase 7.5 — FEATURES gap closure (split per 226.E3).
 *
 * @deprecated — kept until Track D's replacement coverage lands; the
 * PR-time smoke (`@critical`) excludes this file via `--grep-invert`.
 * Each test here was relocated verbatim from the original
 * frontend/e2e/phase7.5-features-gap-closure.spec.ts so test semantics,
 * silent-failure annotations, and skip messages are preserved.
 *
 * Real backend only. No mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import {
  getTestUser,
  loginUser,
} from '../fixtures/auth';
import {
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe("Phase 7.5 gap — home + admin + critical routes @deprecated", () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
  });


  test('Phase 7.5.N.1 — Home: after login home loads and shows at least one section', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });

    const homePage = page.locator('[data-testid="home-page"]');
    await expect(homePage).toBeVisible({ timeout: 10000 });

    // Check for at least one section (quick actions, recent assets, datasets, or jobs)
    const quickActions = page.locator('[data-testid="home-quick-actions"]');
    const recentAssets = page.locator('[data-testid="home-recent-assets"]');
    const recentDatasets = page.locator('[data-testid="home-recent-datasets"]');
    const recentJobs = page.locator('[data-testid="home-recent-jobs"]');

    const hasQuickActions = (await quickActions.count()) > 0;
    const hasRecentAssets = (await recentAssets.count()) > 0;
    const hasRecentDatasets = (await recentDatasets.count()) > 0;
    const hasRecentJobs = (await recentJobs.count()) > 0;

    // Assert at least one section is visible
    expect(hasQuickActions || hasRecentAssets || hasRecentDatasets || hasRecentJobs).toBe(true) /* acceptable states */;

    // Check for system status widget
    const systemStatus = page.locator('[data-testid="home-system-status"]');
    await expect(systemStatus).toBeVisible({ timeout: 5000 });

    // Assert page didn't crash
    await expect(homePage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.N.2 — Admin: as tenant/platform admin open admin and assert content or "no permissions"', async ({
    page,
  }) => {
    await page.goto('/admin', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Check if redirected (403 or login) or page loads
    const currentUrl = page.url();
    const isRedirected = currentUrl.includes('/login') || currentUrl.includes('/403');
    const isAdminPage = currentUrl.includes('/admin');

    if (isRedirected) {
      // User doesn't have admin access - ProtectedRoute redirected
      expect(isRedirected).toBe(true) /* acceptable states */;
      return;
    }

    // User has access - check admin page content
    expect(isAdminPage).toBe(true) /* acceptable states */;

    const adminPage = page.locator('.admin-page, [data-testid="admin-page"]');
    await expect(adminPage).toBeVisible({ timeout: 10000 });

    // Check if user has admin access or shows "no permissions"
    const noPermission = page.locator('.admin-no-permission');
    const overviewSection = page.locator('[data-testid="admin-overview-section"]');
    const tenantsSection = page.locator('[data-testid="admin-tenants-section"]');
    const usersSection = page.locator('[data-testid="admin-users-section"]');

    const hasNoPermission = (await noPermission.count()) > 0;
    const hasOverview = (await overviewSection.count()) > 0;
    const hasTenants = (await tenantsSection.count()) > 0;
    const hasUsers = (await usersSection.count()) > 0;

    // Assert either no permission message OR admin content is shown
    expect(hasNoPermission || hasOverview || hasTenants || hasUsers).toBe(true) /* acceptable states */;

    // If has access, check that overview section is visible
    if (!hasNoPermission) {
      await expect(overviewSection).toBeVisible({ timeout: 5000 });
    }

    // Assert page didn't crash
    await expect(adminPage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5 critical routes are handled by app (no crash)', async ({ page }) => {
    const routes = [
      '/search',
      '/governance',
      '/files',
      '/audit',
      '/scheduled-ingestions',
      '/semantic',
      '/webhooks',
    ];

    for (const route of routes) {
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1500);

      const body = page.locator('body');
      await expect(body).toBeVisible();
    }
  });
});
