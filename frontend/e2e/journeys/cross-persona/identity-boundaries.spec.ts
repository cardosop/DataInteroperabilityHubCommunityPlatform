/**
 * W5.2 (oss-release-remediation R2-F2) — identity-boundary cache hygiene
 * (UI-verified against the real stack).
 *
 * The property: a tenant switch (or an identity end) must never leave the
 * previous identity's CACHED data rendering. Three boundaries are proven:
 *
 *  1. **Query-cache boundary** — the assets list fetched under the primary
 *     tenant must not render after switching to the secondary tenant (the
 *     query client drains at the boundary; pre-W5.2 the cached rows stayed
 *     mounted).
 *  2. **Capability boundary** — the primary tenant's Databricks control
 *     plane is enabled (the e2e seed enables it on the default tenant),
 *     the secondary tenant's is not. The sidebar's Databricks nav item
 *     must disappear after the switch and come back after switching back
 *     (pre-W5.2 the singleton served the previous tenant's snapshot for
 *     up to the 5-minute TTL).
 *  3. **Logout boundary** — after logout the landing page renders and no
 *     cached shell survives (the query client + capabilities drained).
 *
 * Real backend only; no mocks. Reuses the multi-tenancy-isolation setup
 * (test-data-cleanup fixture + ensure-e2e-tenant-switch-setup).
 */

import { expect, test } from '../../fixtures/test-data-cleanup';
import { clearAuthStorage, getTenantAdminUser, gotoWithRetry } from '../../fixtures/auth';
import { e2eTestHeaders } from '../../fixtures/e2e-token';
import { loginAndNavigateToRoute, switchTenantViaUI } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

const DATABRICKS_NAV = '.nav-label:has-text("Databricks")';

test.describe('Identity-boundary caches (W5.2)', () => {
  test.setTimeout(180000);

  test(
    'login → switch-tenant → switch-back → logout never renders cross-identity data',
    async ({ page, cleanup }) => {
      await clearAuthStorage(page);
      // The TENANT_ADMIN persona — the Databricks nav item (the
      // capability-boundary probe) is role-gated to TENANT_ADMIN/
      // PLATFORM_ADMIN, and the default tenant (this user's home) has
      // databricks_control_plane_enabled=True via the e2e seed.
      const user = await getTenantAdminUser();

      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"]',
      });

      const accessToken = await page.evaluate(() => {
        const getter = (window as unknown as { __getAccessToken?: () => string | null })
          .__getAccessToken;
        return typeof getter === 'function' ? getter() : localStorage.getItem('access_token');
      });
      if (!accessToken) {
        throw new Error(
          'No access_token after loginAndNavigateToRoute — cookie/storage policy ' +
            'may be blocking the session; check the browser context and login flow.'
        );
      }
      const headers = { Authorization: `Bearer ${accessToken}` };

      // Ensure the user has the secondary tenant (same contract as the
      // multi-tenancy-isolation spec — a 404 here is a misconfiguration
      // to surface, never a skip).
      const setupRes = await page.request.post(
        `${API_BASE}/test/ensure-e2e-tenant-switch-setup/`,
        { headers: { ...headers, ...e2eTestHeaders() } }
      );
      if (!setupRes.ok()) {
        // intentional: diagnostic extraction — a failed read yields '' for the error message; the throw below is the failure path
        const body = await setupRes.text().catch(() => '');
        throw new Error(
          `ensure-e2e-tenant-switch-setup returned ${setupRes.status()}. Body (first 300): ${body.slice(0, 300)}`
        );
      }
      const setup = (await setupRes.json()) as {
        primary_tenant_name: string;
        secondary_tenant_name: string;
      };

      // ── Primary-tenant asset (unique; tracked for cleanup) ────────────────
      const uniqueAssetKey = `e2e-identity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const uniqueAssetName = `E2E Identity ${Date.now()}`;
      const createResp = await page.request.post(`${API_BASE}/assets/`, {
        headers: { ...headers, 'Content-Type': 'application/json' },
        data: {
          key: uniqueAssetKey,
          name: uniqueAssetName,
          description: 'Created by E2E identity-boundaries test',
          visibility: 'INTERNAL',
        },
      });
      if (!createResp.ok()) {
        throw new Error(`Asset creation for identity-boundaries failed with HTTP ${createResp.status()}.`);
      }
      const assetData = (await createResp.json()) as { id?: string; key?: string };
      if (!assetData.id) {
        throw new Error('Asset creation returned 2xx without an id — backend-contract regression.');
      }
      cleanup.track({ type: 'asset', id: assetData.id, owner: user });
      const assetIdentifier = assetData.key ?? uniqueAssetKey;

      // ── Boundary 2 pre-state: primary tenant HAS the Databricks nav ───────
      // (the e2e seed enables databricks_control_plane_enabled on the
      // default tenant; the secondary tenant keeps the default OFF).
      await gotoWithRetry(page, '/');
      await page.waitForSelector('.app-sidebar, [data-testid="app-header"]', { timeout: 15000 });
      await expect(page.locator(DATABRICKS_NAV).first()).toBeVisible({ timeout: 15000 });

      // ── Populate the query cache: the primary assets list ─────────────────
      await page.goto('/assets');
      await page.waitForSelector(
        '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"]',
        { timeout: 20000 }
      );
      await expect(page.locator(`text="${assetIdentifier}"`).first()).toBeVisible({
        timeout: 15000,
      });

      // ── SWITCH to the secondary tenant ────────────────────────────────────
      await gotoWithRetry(page, '/');
      await page.waitForSelector('.app-sidebar, [data-testid="app-header"]', { timeout: 15000 });
      const { newTenantName } = await switchTenantViaUI(page, setup.secondary_tenant_name);
      expect(newTenantName).toContain(setup.secondary_tenant_name);

      // Boundary 2 (capability): the Databricks nav must be GONE — the
      // capabilities cache is tenant-keyed (pre-W5.2: the primary's
      // snapshot kept serving for the TTL and the item stayed mounted).
      await expect(page.locator(DATABRICKS_NAV)).toHaveCount(0, { timeout: 15000 });

      // Boundary 1 (query cache): the primary tenant's asset must NOT
      // render in the secondary tenant's list — the query client drained
      // at the switch and refetched under the new identity.
      await page.goto('/assets');
      await page.waitForSelector(
        '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        { timeout: 20000 }
      );
      const assetInSecondaryTenant = await page.locator(`text="${assetIdentifier}"`).count();
      expect(
        assetInSecondaryTenant,
        `IDENTITY-BOUNDARY BREACH: asset "${assetIdentifier}" created in ${setup.primary_tenant_name} ` +
          `is still rendering (${assetInSecondaryTenant}x) after switching to ` +
          `${setup.secondary_tenant_name} — the query cache survived the tenant ` +
          `switch. The identity cache boundary (queryClient.clear() + ` +
          `cancelQueries) is not draining.`
      ).toBe(0);

      // ── SWITCH BACK: both surfaces return from their own caches ───────────
      await gotoWithRetry(page, '/');
      await page.waitForSelector(
        '[data-testid="home-page"], .app-sidebar, [data-testid="app-header"]',
        { timeout: 45000 }
      );
      const { newTenantName: restoredName } = await switchTenantViaUI(
        page,
        setup.primary_tenant_name
      );
      expect(restoredName).toContain(setup.primary_tenant_name);

      await expect(page.locator(DATABRICKS_NAV).first()).toBeVisible({ timeout: 15000 });
      await page.goto('/assets');
      await page.waitForSelector(
        '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"]',
        { timeout: 20000 }
      );
      await expect(page.locator(`text="${assetIdentifier}"`).first()).toBeVisible({
        timeout: 15000,
      });

      // ── Boundary 3: LOGOUT ends the identity ──────────────────────────────
      await page.locator('.user-menu-trigger').first().click();
      await page.locator('.user-menu-logout').first().click();
      // The landing/login surface renders (no cached shell survives the
      // identity end; the login-submit testid is the login-page marker).
      await page.waitForSelector('[data-testid="login-submit"], [data-testid="landing-page"]', {
        timeout: 20000,
      });
      const storedUser = await page.evaluate(() => localStorage.getItem('user'));
      expect(storedUser).toBeNull();
    }
  );
});
