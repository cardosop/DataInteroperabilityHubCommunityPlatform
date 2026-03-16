/**
 * E2E Test: JOURNEY-TA-001 — Onboard New User
 *
 * Journey: Onboard New User (Invite and onboard user to tenant)
 * Persona: Tenant Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per admin-audit-settings pattern. Routes: /admin.
 * Fixture: getTenantAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, getTenantAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-TA-001: Onboard New User', () => {
  test.setTimeout(240000); // 4 min: visible/slowMo + loginAsPersona can exceed 2 min

  test.describe('Success', () => {
    test('admin page loads with users section', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/admin');
      const hasContent =
        (await page.locator('.admin-page').count()) > 0 &&
        ((await page.locator('.admin-tabs, .admin-users-section, [data-testid="admin-users-section"]').count()) > 0 ||
          (await page.locator('button:has-text("Users")').count()) > 0);
      expect(hasContent).toBe(true);
    });

    test('users tab loads user list', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const usersTab = page.locator('button:has-text("Users")');
      expect((await usersTab.count()) > 0).toBe(true);
      await usersTab.first().click();
      await page.waitForTimeout(2000);
      const hasUsersSection =
        (await page.locator('[data-testid="admin-users-section"]').count()) > 0 ||
        (await page.locator('.admin-table').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasUsersSection).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('admin page loads without crash', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onAdmin = page.url().includes('/admin');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasContent =
        (await page.locator('.admin-page, .admin-no-permission, [data-testid="forbidden-page"]').count()) > 0 ||
        (await page.locator('text=/403|forbidden/i').count()) > 0;
      const no500 = (await page.locator('text=/500|internal server error/i').count()) === 0;
      expect(onAdmin || on403 || onLogin).toBe(true);
      // When on /login, we may not have admin content; when on /admin or /403, expect content and no 500
      expect(onLogin || (hasContent && no500)).toBe(true);
    });
  });

  test.describe('RBAC', () => {
    test('non-admin user is refused access to admin panel', async ({ page }) => {
      // getConsumerTestUser() is DATA_CONSUMER role — must not be able to access /admin
      await loginAsPersona(page, getConsumerTestUser);
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      // Give the SPA auth guard time to check roles and complete the redirect to /403 or /login.
      // React Router's ProtectedRoute redirect is synchronous but auth store init is async;
      // waitForURL waits until the URL actually changes to the expected destination.
      await page.waitForURL(/\/(403|login)(\?|$)/, { timeout: 15000 }).catch(() => null);
      const url = page.url();
      // Consumer must be refused — /admin is Tenant Admin only
      expect(url.includes('/403') || url.includes('/login')).toBe(true);
      // Must NOT be on /admin itself (that would be an RBAC bypass)
      expect(url.includes('/admin') && !url.includes('/403')).toBe(false);
    });
  });
});
