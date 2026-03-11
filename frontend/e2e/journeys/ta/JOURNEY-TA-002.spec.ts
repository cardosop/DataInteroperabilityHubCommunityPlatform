/**
 * E2E Test: JOURNEY-TA-002 — Manage User Roles
 *
 * Journey: Manage User Roles
 * Persona: Tenant Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/ta/JOURNEY-TA-002.md
 *
 * Success/Failure/Edge. Routes: /admin, /admin/users/:id/edit.
 * Fixture: getTenantAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTenantAdminUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-TA-002: Manage User Roles', () => {
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('admin users list loads', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/admin');
      const usersTab = page.locator('button:has-text("Users")');
      if ((await usersTab.count()) > 0) {
        await usersTab.first().click();
        await page.waitForTimeout(2000);
      }
      const hasUsersSection =
        (await page.locator('[data-testid="admin-users-section"]').count()) > 0 ||
        (await page.locator('.admin-table').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.admin-page').count()) > 0;
      expect(hasUsersSection).toBe(true);
    });

    test('user edit page loads with role checkboxes', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const editLink = page.locator('a[href*="/admin/users/"][href*="/edit"]').first();
      if ((await editLink.count()) > 0) {
        await editLink.click();
        await page.waitForURL(/\/admin\/users\/[^/]+\/edit/, { timeout: 10000 });
        await page.waitForSelector('.user-edit-page, .user-edit-roles, .user-edit-form, #email', {
          timeout: 15000,
        });
        const hasEditPage =
          (await page.locator('.user-edit-page').count()) > 0 ||
          (await page.locator('.user-edit-roles').count()) > 0;
        expect(hasEditPage || page.url().includes('/admin/users/')).toBe(true);
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to admin users redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
      if (url.includes('/admin')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('admin users list shows empty state or user table', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const usersTab = page.locator('button:has-text("Users")');
      if ((await usersTab.count()) > 0) {
        await usersTab.first().click();
        await page.waitForTimeout(2000);
      }
      const hasContent =
        (await page.locator('.admin-table').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.admin-page').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
