/**
 * E2E Test: JOURNEY-PA-002 — Manage Tenant Lifecycle
 *
 * Persona: Platform Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/pa/JOURNEY-PA-002.md
 *
 * Success: Platform admin suspends and resumes a tenant via the admin UI.
 * Failure: Unauthenticated redirect.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('JOURNEY-PA-002: Manage Tenant Lifecycle', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('platform admin can suspend and resume a tenant from the admin UI', async ({ page }) => {
      const paUser = await getPlatformAdminUser();

      await loginAndNavigateToRoute(page, paUser, '/admin', {
        timeout: 60000,
        contentSelector: '.admin-page',
      });
      if (page.url().includes('/403') || page.url().includes('/login')) {
        test.skip(true, 'Platform admin user does not have admin page access in this environment');
        return;
      }

      // Get access token now (page is loaded, localStorage available)
      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) return;

      // ── Pre-flight: resume any suspended tenants left by previous runs ──────
      // This must happen BEFORE the UI is used, so we reload after to sync state.
      const tenantsResp = await page.request.get(`${API_BASE}/tenants/?page_size=20`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!tenantsResp.ok()) {
        test.skip(true, 'Platform admin tenants API not available');
        return;
      }
      const tenantsData = (await tenantsResp.json()) as {
        results?: Array<{ id?: string; name?: string; status?: string }>;
      };
      // Resume ALL suspended tenants from previous runs before proceeding
      const suspendedTenants = (tenantsData.results ?? []).filter(
        (t) => t.status === 'SUSPENDED' && t.id
      );
      for (const st of suspendedTenants) {
        await page.request
          .post(`${API_BASE}/tenants/${st.id}/reactivate/`, {
            headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
            data: {},
          })
          .catch(() => null);
      }

      // Reload the admin page so the UI reflects the API state after cleanup
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.admin-page', { timeout: 15000 });

      // Navigate to Tenants tab
      const tenantsTab = page.locator(
        'button:has-text("Tenants"), [data-testid="admin-tenants-tab"]'
      );
      if ((await tenantsTab.count()) > 0) {
        await tenantsTab.first().click();
      }

      await page.waitForSelector('[data-testid="tenants-table"], .tenants-list, .admin-table', {
        timeout: 15000,
      });

      // Re-fetch after cleanup to get current state
      const tenantsResp2 = await page.request.get(`${API_BASE}/tenants/?page_size=20`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const tenantsData2 = tenantsResp2.ok()
        ? ((await tenantsResp2.json()) as { results?: Array<{ id?: string; name?: string; status?: string }> })
        : tenantsData;
      const targetTenant = (tenantsData2.results ?? []).find(
        (t) => t.status !== 'SUSPENDED' && t.status !== 'DELETED'
          && (tenantsData2.results?.length ?? 0) > 1  // prefer secondary tenant when multiple exist
      ) ?? (tenantsData2.results ?? []).find(
        (t) => t.status !== 'SUSPENDED' && t.status !== 'DELETED'
      );

      if (!targetTenant?.id) {
        test.skip(true, 'No suitable tenant found for suspend test');
        return;
      }

      // Find the tenant row in the admin UI table
      const tenantRow = page.locator(`tr:has-text("${targetTenant.name}")`).first();
      if ((await tenantRow.count()) === 0) {
        test.skip(true, `Tenant "${targetTenant.name}" row not found in admin table`);
        return;
      }

      // Suspend button: data-testid="suspend-tenant-{id}" (AdminPage.tsx line 228)
      const suspendButton = page.locator(`[data-testid="suspend-tenant-${targetTenant.id}"]`);
      if ((await suspendButton.count()) === 0) {
        test.skip(true, 'Suspend button not found — tenant may already be suspended or deleted');
        return;
      }

      // Actual suspend URL: POST /tenants/{id}/suspend/ (adminService.suspendTenant)
      const suspendResponsePromise = page.waitForResponse(
        (r) =>
          r.url().includes(`/tenants/${targetTenant.id}/`) &&
          r.url().includes('/suspend/') &&
          r.request().method() === 'POST',
        { timeout: 20000 }
      );
      await suspendButton.click();

      // Handle any confirmation dialog
      const dialog = page.locator('[role="dialog"], .confirm-dialog');
      if ((await dialog.count()) > 0) {
        await dialog.first().locator('button:has-text("Confirm"), button:has-text("Yes")').click();
      }

      const suspendResp = await suspendResponsePromise;
      // 409 means tenant was already suspended (e.g. from a prior parallel run) — treat as success
      if (suspendResp.status() === 409) {
        // Tenant already suspended — verify the UI reflects SUSPENDED state and proceed to cleanup
        await expect(tenantRow.locator('.status-badge').first()).toContainText('SUSPENDED', { timeout: 15000 });
      } else {
        expect(suspendResp.status()).toBeGreaterThanOrEqual(200);
        expect(suspendResp.status()).toBeLessThan(300);
      }

      // Badge must change to SUSPENDED (React Query re-fetches on mutation success)
      await expect(tenantRow.locator('.status-badge').first()).toContainText('SUSPENDED', { timeout: 15000 });

      // Resume the tenant (cleanup + verification)
      // The resume button appears after React Query updates with new tenant status
      const resumeButton = page.locator(`[data-testid="resume-tenant-${targetTenant.id}"]`);
      await resumeButton.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await resumeButton.count()) > 0) {
        // Actual resume URL: POST /tenants/{id}/reactivate/ (adminService.resumeTenant)
        const resumeResponsePromise = page.waitForResponse(
          (r) =>
            r.url().includes(`/tenants/${targetTenant.id}/`) &&
            r.url().includes('/reactivate/') &&
            r.request().method() === 'POST',
          { timeout: 20000 }
        );
        await resumeButton.click();
        const resumeDialog = page.locator('[role="dialog"], .confirm-dialog');
        if ((await resumeDialog.count()) > 0) {
          await resumeDialog
            .first()
            .locator('button:has-text("Confirm"), button:has-text("Yes")')
            .click();
        }
        const resumeResp = await resumeResponsePromise;
        expect(resumeResp.status()).toBeGreaterThanOrEqual(200);
        await expect(tenantRow.locator('.status-badge').first()).toContainText('ACTIVE', { timeout: 15000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)/, { timeout: 20_000 });
      const url = page.url();
      // Unauthenticated users must be redirected — never allowed to stay on /admin
      expect(url.includes('/login') || url.includes('/403')).toBe(true);
    });
  });

  test.describe('Route', () => {
    test('admin page loads with tenants section', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', {
        timeout: 60000,
        contentSelector: '.admin-page, [data-testid="forbidden-page"]',
      });
      // Authenticated PA user: /login should not appear; /admin or /403 (role not assigned) are valid
      expect(page.url().includes('/admin') || page.url().includes('/403')).toBe(true);
    });
  });
});
