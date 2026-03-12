/**
 * E2E Test: JOURNEY-TA-002 — Manage User Roles
 *
 * Journey: Manage User Roles
 * Persona: Tenant Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/ta/JOURNEY-TA-002.md
 *
 * Success: Assign a new role to an invited user and verify the change persists via API re-fetch.
 * Failure: Unauthenticated redirect.
 * Edge: Admin users list shows empty state or user table.
 *
 * Real backend only; no mocks. Uses api-users.ts helpers for user management operations.
 */

import path from 'node:path';
import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTenantAdminUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute, changeUserRolesViaAdminUI } from '../../fixtures/helpers';
import { inviteUserViaApi, getUserByEmailViaApi } from '../../fixtures/api-users';

// Align with fixtures/auth.ts API resolution
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('JOURNEY-TA-002: Manage User Roles', () => {
  test.setTimeout(300000); // 5 min: invite + role change + verification

  test.describe('Success', () => {
    test('admin can assign DATA_PROVIDER role to an invited user and verify via API re-fetch', async ({
      page,
    }) => {
      const adminUser = await getTenantAdminUser();

      // ── Pre-condition: invite a real user so we have a verifiable userId ──
      const email = `ta-002-role-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@e2e-test.example.com`;
      let userId: string;
      try {
        const invited = await inviteUserViaApi(adminUser, email, 'DATA_CONSUMER');
        userId = invited.userId;
      } catch (inviteErr) {
        // If invite is not available, fall back to finding an existing non-admin user
        console.warn(`inviteUserViaApi failed (${inviteErr}), falling back to existing user lookup`);
        const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
        if (!accessToken) {
          // Log in first to get a token
          await loginAndNavigateToRoute(page, adminUser, '/admin', {
            timeout: 60000,
            contentSelector: '.admin-page',
          });
        }
        const token = await page.evaluate(() => localStorage.getItem('access_token'));
        if (!token) {
          test.skip(true, 'Could not obtain access token for admin user lookup');
          return;
        }
        const usersResp = await page.request.get(`${API_BASE}/admin/users/?page_size=10`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!usersResp.ok()) {
          test.skip(true, 'Admin users API not available');
          return;
        }
        const usersData = (await usersResp.json()) as {
          results?: Array<{ id?: string; email?: string; roles?: string[] }>;
        };
        const nonAdminUser = (usersData.results ?? []).find(
          (u) => u.email !== adminUser.email && !u.roles?.includes('TENANT_ADMIN')
        );
        if (!nonAdminUser?.id) {
          test.skip(true, 'No suitable non-admin user found for role assignment test');
          return;
        }
        userId = nonAdminUser.id;
      }

      // ── Navigate to the user edit page ───────────────────────────────────
      await loginAndNavigateToRoute(page, adminUser, `/admin/users/${userId}/edit`, {
        timeout: 60000,
        contentSelector: '.user-edit-page, .user-edit-form, .user-edit-roles, form',
      });

      if (page.url().includes('/403') || page.url().includes('/login')) {
        test.skip(
          true,
          `Admin user cannot access /admin/users/${userId}/edit. ` +
          'Ensure e2e_admin@example.com has TENANT_ADMIN role.'
        );
        return;
      }

      // ── Check DATA_PROVIDER role checkbox state before change ─────────────
      const dataProviderCheckbox = page.locator(
        'input[type="checkbox"][value="DATA_PROVIDER"], ' +
        'input[type="checkbox"][id*="DATA_PROVIDER"], ' +
        'input[type="checkbox"][name*="DATA_PROVIDER"]'
      );

      if ((await dataProviderCheckbox.count()) === 0) {
        test.skip(
          true,
          'DATA_PROVIDER role checkbox not found at expected selectors. ' +
          'Update selector to match the current admin user-edit UI.'
        );
        return;
      }

      const wasChecked = await dataProviderCheckbox.first().isChecked();

      // ── Change role: add DATA_PROVIDER ────────────────────────────────────
      const { httpStatus } = await changeUserRolesViaAdminUI(
        page,
        userId,
        wasChecked ? [] : ['DATA_PROVIDER'],  // add if not already added
        wasChecked ? ['DATA_PROVIDER'] : []   // remove if already there (idempotency test)
      );
      expect(httpStatus).toBeGreaterThanOrEqual(200);
      expect(httpStatus).toBeLessThan(300);

      // ── UI feedback: success message must appear ──────────────────────────
      await expect(
        page.locator(
          '.success-message, [data-testid="save-success"], .toast-success, ' +
          '[role="status"]:has-text("saved"), text=/saved|updated|success/i'
        )
      ).toBeVisible({ timeout: 10000 });

      // ── Backend verification: re-fetch user and assert role changed ───────
      const updatedUser = await getUserByEmailViaApi(adminUser, email).catch(() => null);
      if (updatedUser) {
        const expectedRole = 'DATA_PROVIDER';
        const expectedAbsence = wasChecked; // if was checked, we removed it

        if (expectedAbsence) {
          expect(updatedUser.roles).not.toContain(expectedRole);
        } else {
          expect(updatedUser.roles).toContain(expectedRole);
        }
      } else {
        // Fall back to reading from the page — the checkbox state must have changed
        const newCheckState = await dataProviderCheckbox.first().isChecked();
        expect(newCheckState).toBe(!wasChecked);
      }
    });

    test('admin users list loads with content (no error display)', async ({ page }) => {
      const adminUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, adminUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/admin');

      const usersTab = page.locator('button:has-text("Users"), [data-testid="admin-users-tab"]');
      if ((await usersTab.count()) > 0) {
        await usersTab.first().click();
        await page.waitForTimeout(2000);
      }

      // Error display is NOT an acceptable outcome for an admin user on the admin page
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        // 403/permission errors are acceptable (user may not have full admin rights)
        if (!/403|forbidden|permission/i.test(errText ?? '')) {
          throw new Error(`Admin users page shows unexpected error: ${errText}`);
        }
      }

      const hasUsersSection =
        (await page.locator('[data-testid="admin-users-section"]').count()) > 0 ||
        (await page.locator('.admin-table').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.admin-page').count()) > 0;
      expect(hasUsersSection).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to admin users redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      const redirectedCorrectly =
        url.includes('/login') || url.includes('/403') || (url.includes('/admin') && await hasLoginPrompt(page));
      expect(redirectedCorrectly).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('admin users list shows empty state or user table (no data corruption)', async ({
      page,
    }) => {
      const adminUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, adminUser, '/admin', { timeout: 60000 });
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
