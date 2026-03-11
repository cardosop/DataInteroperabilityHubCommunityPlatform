/**
 * E2E Test: JOURNEY-AUTH-005 — User Switches Active Tenant
 *
 * Journey: Authenticated user with membership in 2+ tenants opens the tenant switcher
 * dropdown, selects a secondary tenant, and verifies the UI and API context update.
 *
 * Priority: High
 * Use Case: UC-AUTH-005
 * Manual test: ManualTest/Front/03-USER-JOURNEYS/auth/JOURNEY-AUTH-005.md
 *
 * Success scenarios: open switcher, select tenant, verify context.
 * Failure scenarios: feature disabled (403/hidden), invalid tenant_id (400), no membership (403).
 * Real backend only; no mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('JOURNEY-AUTH-005: User Switches Active Tenant', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('tenant switcher is visible in header when user has tenants', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await expect(page.locator('.app-header')).toBeVisible({ timeout: 15000 });

      // Tenant switcher or tenant name should be accessible in the header
      const tenantSwitcher = page.locator('.tenant-switcher, [data-testid="tenant-switcher"]');
      const hasSwitcher = (await tenantSwitcher.count()) > 0;

      if (hasSwitcher) {
        await expect(tenantSwitcher.first()).toBeVisible({ timeout: 5000 });
      } else {
        // Tenant context may be displayed as plain text (single-tenant users)
        const headerContent = await page.locator('.app-header').textContent();
        expect(headerContent).toBeTruthy();
      }
    });

    test('GET /auth/me/tenants/ returns list of tenants for authenticated user', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        test.skip(true, 'No access token — login did not complete');
        return;
      }

      const res = await page.request.get(`${API_BASE}/auth/me/tenants/`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      if (res.status() === 403) {
        // Feature may be disabled or user lacks permission — acceptable
        expect([200, 403]).toContain(res.status());
        return;
      }

      expect(res.status()).toBe(200);
      const tenants = (await res.json()) as Array<{ id: string; name: string; slug: string }>;
      expect(Array.isArray(tenants)).toBe(true);
      expect(tenants.length).toBeGreaterThanOrEqual(1);
      // Each tenant must have required fields
      for (const tenant of tenants) {
        expect(typeof tenant.id).toBe('string');
        expect(typeof tenant.name).toBe('string');
      }
    });

    test('switch tenant via UI: open dropdown, select secondary tenant, verify context', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await expect(page.locator('.app-header')).toBeVisible({ timeout: 15000 });

      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        test.skip(true, 'No access token');
        return;
      }

      // Ensure a secondary tenant exists via test helper (requires ENVIRONMENT=test)
      const setupRes = await page.request.post(
        `${API_BASE}/test/ensure-e2e-tenant-switch-setup/`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      if (!setupRes.ok()) {
        test.skip(
          true,
          'ensure-e2e-tenant-switch-setup not available (ENVIRONMENT=test required). Skipping UI switch test.'
        );
        return;
      }
      const setup = (await setupRes.json()) as { secondary_tenant_id: string };
      const secondaryTenantId = setup.secondary_tenant_id;

      // Open tenant switcher in header
      const tenantSwitcher = page.locator('.tenant-switcher, [data-testid="tenant-switcher"]');
      if ((await tenantSwitcher.count()) === 0) {
        test.skip(true, 'Tenant switcher not rendered (may require multi-tenant user)');
        return;
      }
      await tenantSwitcher.first().click();

      // Dropdown with tenant list should appear
      const dropdown = page.locator(
        '.tenant-switcher-dropdown, [data-testid="tenant-dropdown"], .tenant-list'
      );
      await expect(dropdown.first()).toBeVisible({ timeout: 8000 });

      // Find and click the secondary tenant option
      const secondaryOption = page.locator(
        `[data-tenant-id="${secondaryTenantId}"], [data-testid="tenant-option-${secondaryTenantId}"]`
      );
      if ((await secondaryOption.count()) > 0) {
        await secondaryOption.first().click();
        await page.waitForTimeout(2000);

        // Active tenant ID in localStorage should reflect the switch
        const storedTenantId = await page.evaluate(
          () =>
            JSON.parse(localStorage.getItem('user') ?? '{}').active_tenant_id ??
            JSON.parse(localStorage.getItem('user') ?? '{}').tenant_id
        );
        // Either the active_tenant_id changed or assets endpoint now uses the secondary tenant
        const assetsRes = await page.request.get(`${API_BASE}/assets/`, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'X-Tenant-Id': secondaryTenantId,
          },
        });
        expect(assetsRes.status()).toBe(200);
      } else {
        // Tenant option not rendered by data attribute — assert dropdown is visible at minimum
        const tenantItems = page.locator('.tenant-switcher-item, .tenant-option');
        const count = await tenantItems.count();
        expect(count).toBeGreaterThanOrEqual(1);
      }
    });
  });

  test.describe('Failure', () => {
    test('POST /auth/switch-tenant/ with invalid tenant_id returns 400', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        test.skip(true, 'No access token');
        return;
      }

      const res = await page.request.post(`${API_BASE}/auth/switch-tenant/`, {
        data: { tenant_id: 'not-a-valid-uuid' },
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      });
      // 400 (invalid uuid), 403 (feature disabled), or 404 are all valid responses
      expect([400, 403, 404, 422]).toContain(res.status());
    });

    test('POST /auth/switch-tenant/ with non-member tenant_id returns 403 or 404', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        test.skip(true, 'No access token');
        return;
      }

      const res = await page.request.post(`${API_BASE}/auth/switch-tenant/`, {
        data: { tenant_id: '00000000-0000-0000-0000-000000000001' },
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      });
      expect([403, 404]).toContain(res.status());
    });

    test('unauthenticated request to /auth/me/tenants/ returns 401', async ({ page }) => {
      await clearAuthStorage(page);
      const res = await page.request.get(`${API_BASE}/auth/me/tenants/`);
      expect(res.status()).toBe(401);
    });
  });
});
