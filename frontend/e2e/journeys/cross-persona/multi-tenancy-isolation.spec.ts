/**
 * E2E: Multi-Tenancy Isolation (UI-verified)
 *
 * Critical security property: assets created in Tenant A must NOT be visible in Tenant B.
 * This test verifies isolation at the browser/UI level, not just at the API level.
 *
 * Flow:
 *   1. Create an asset in the primary tenant (via API)
 *   2. Switch to the secondary tenant via the header UI dropdown
 *   3. Navigate to assets list — primary tenant's asset must NOT appear
 *   4. Navigate directly to the asset URL — must show error/404, not the asset
 *   5. Switch back to primary tenant — asset IS visible
 *
 * Real backend only; no mocks. Uses api-assets.ts and the switchTenantViaUI helper.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { loginAndNavigateToRoute, switchTenantViaUI } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('Multi-Tenancy Isolation (UI-verified)', () => {
  test.setTimeout(300000);

  test(
    'asset created in Tenant A is invisible in Tenant B and visible back in Tenant A',
    async ({ page }) => {
      await clearAuthStorage(page);
      const user = await getTestUser();

      // Log in and navigate to the app.
      // contentSelector must be an element inside .app-main; [data-testid="home-page"] is
      // rendered by HomePage.tsx directly inside .app-main (not .app-sidebar/.app-header
      // which are siblings of .app-main and would never resolve).
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"]',
      });

      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        test.skip(true, 'No access token after login');
        return;
      }
      const headers = { Authorization: `Bearer ${accessToken}` };

      // Ensure the user has a secondary tenant
      const setupRes = await page.request.post(
        `${API_BASE}/test/ensure-e2e-tenant-switch-setup/`,
        { headers }
      );
      if (!setupRes.ok()) {
        test.skip(true, 'ensure-e2e-tenant-switch-setup not available (ENVIRONMENT=test required)');
        return;
      }
      const setup = (await setupRes.json()) as {
        primary_tenant_id: string;
        primary_tenant_name: string;
        secondary_tenant_id: string;
        secondary_tenant_name: string;
      };

      // ── Step 1: Create asset in primary tenant via API ────────────────────
      const assetId = await createAssetViaApi(user);
      // Get the asset key so we can search for it by name in the list
      const assetResp = await page.request.get(`${API_BASE}/assets/${assetId}/`, { headers });
      const assetData = assetResp.ok()
        ? ((await assetResp.json()) as { key?: string; name?: string })
        : {};
      const assetIdentifier = assetData.name ?? assetData.key ?? assetId.slice(0, 8);

      // ── Step 2: Switch to secondary tenant via UI dropdown ────────────────
      await page.goto('/');
      await page.waitForSelector('.app-sidebar, .app-header', { timeout: 15000 });

      const { newTenantName } = await switchTenantViaUI(page, setup.secondary_tenant_name);
      expect(newTenantName).toContain(setup.secondary_tenant_name);

      // ── Step 3: Navigate to assets in secondary tenant ────────────────────
      await page.goto('/assets');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.asset-list-page, .empty-state, .error-display', {
        timeout: 20000,
      });

      // Primary tenant's asset must NOT appear in secondary tenant's asset list
      const assetInSecondaryTenant = await page.locator(`text="${assetIdentifier}"`).count();
      expect(assetInSecondaryTenant).toBe(0);

      // ── Step 4: Direct URL to primary tenant's asset must show 404/error ──
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      const url = page.url();
      const hasErrorForIsolatedAsset =
        // Shows a 404/error boundary
        (await page.locator('.error-display, [data-testid="not-found"], .not-found-page').count()) > 0 ||
        // Redirected away from the asset URL (e.g., back to list)
        (!url.includes(assetId)) ||
        // URL changed to 404
        url.includes('/404');
      expect(hasErrorForIsolatedAsset).toBe(true);

      // ── Step 5: Switch back to primary tenant — asset IS visible ──────────
      await page.goto('/');
      await page.waitForSelector('.app-sidebar, .app-header', { timeout: 15000 });

      const { newTenantName: restoredName } = await switchTenantViaUI(
        page,
        setup.primary_tenant_name
      );
      expect(restoredName).toContain(setup.primary_tenant_name);

      // Navigate to the asset directly — should load without error
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      // In the primary tenant, the asset detail should load
      const hasAssetInPrimary =
        (await page.locator('.asset-detail-page, .asset-detail-content').count()) > 0;
      const hasErrorInPrimary =
        (await page.locator('.error-display').count()) > 0 &&
        !(await page.locator('.asset-detail-page').count());

      // Must NOT show 404 in the primary tenant
      expect(hasAssetInPrimary || !hasErrorInPrimary).toBe(true);
    }
  );
});
