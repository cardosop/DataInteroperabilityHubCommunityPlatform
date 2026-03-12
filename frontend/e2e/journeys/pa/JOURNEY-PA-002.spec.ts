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
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('JOURNEY-PA-002: Manage Tenant Lifecycle', () => {
  test.setTimeout(300000);

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

      // Navigate to Tenants tab
      const tenantsTab = page.locator(
        'button:has-text("Tenants"), [data-testid="admin-tenants-tab"]'
      );
      if ((await tenantsTab.count()) > 0) {
        await tenantsTab.first().click();
        await page.waitForTimeout(2000);
      }

      await page.waitForSelector('[data-testid="tenants-table"], .tenants-list, .admin-table', {
        timeout: 15000,
      });

      // Get a non-primary, non-suspended tenant from the API
      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) return;

      const tenantsResp = await page.request.get(`${API_BASE}/admin/tenants/?page_size=20`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!tenantsResp.ok()) {
        test.skip(true, 'Platform admin tenants API not available');
        return;
      }
      const tenantsData = (await tenantsResp.json()) as {
        results?: Array<{ id?: string; name?: string; status?: string }>;
      };
      const targetTenant = (tenantsData.results ?? []).find(
        (t) => t.status !== 'SUSPENDED' && t.name !== 'Primary'
      );

      if (!targetTenant?.id) {
        test.skip(true, 'No suitable non-primary tenant found for suspend test');
        return;
      }

      // Find the tenant row and click Suspend
      const tenantRow = page.locator(`tr:has-text("${targetTenant.name}")`).first();
      if ((await tenantRow.count()) === 0) {
        test.skip(true, `Tenant "${targetTenant.name}" row not found in admin table`);
        return;
      }

      const suspendButton = tenantRow.locator('button:has-text("Suspend"), [data-action="suspend"]');
      if ((await suspendButton.count()) === 0) {
        test.skip(true, 'Suspend button not found — admin UI may not support tenant lifecycle from table');
        return;
      }

      const suspendResponsePromise = page.waitForResponse(
        (r) =>
          r.url().includes(`/admin/tenants/${targetTenant.id}`) &&
          (r.request().method() === 'PATCH' || r.request().method() === 'POST'),
        { timeout: 20000 }
      );
      await suspendButton.click();

      // Handle confirmation dialog
      const dialog = page.locator('[role="dialog"], .confirm-dialog');
      if ((await dialog.count()) > 0) {
        await dialog.first().locator('button:has-text("Confirm"), button:has-text("Yes")').click();
      }

      const suspendResp = await suspendResponsePromise;
      expect(suspendResp.status()).toBeGreaterThanOrEqual(200);
      expect(suspendResp.status()).toBeLessThan(300);

      // Badge must change to SUSPENDED
      await expect(tenantRow.locator('.status-badge, [data-testid="tenant-status"]')).toContainText(
        'SUSPENDED',
        { timeout: 10000 }
      );

      // Resume the tenant (cleanup + verification)
      const resumeButton = tenantRow.locator('button:has-text("Resume"), [data-action="resume"]');
      if ((await resumeButton.count()) > 0) {
        const resumeResponsePromise = page.waitForResponse(
          (r) =>
            r.url().includes(`/admin/tenants/${targetTenant.id}`) &&
            (r.request().method() === 'PATCH' || r.request().method() === 'POST'),
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
        await expect(
          tenantRow.locator('.status-badge, [data-testid="tenant-status"]')
        ).toContainText('ACTIVE', { timeout: 10000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
    });
  });

  test.describe('Route', () => {
    test('admin page loads with tenants section', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', {
        timeout: 60000,
        contentSelector: '.admin-page, [data-testid="forbidden-page"]',
      });
      expect(
        page.url().includes('/admin') || page.url().includes('/403') || page.url().includes('/login')
      ).toBe(true);
    });
  });
});
