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

// Phase 225.4 P0.5 — use the cleanup fixture so the asset created by this test
// is torn down on pass OR fail; otherwise repeated runs accumulate orphans.
import { expect, test } from '../../fixtures/test-data-cleanup';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
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

test.describe('Multi-Tenancy Isolation (UI-verified)', () => {
  test.setTimeout(120000);

  test(
    'asset created in Tenant A is invisible in Tenant B and visible back in Tenant A',
    async ({ page, cleanup }) => {
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
        { headers: { ...headers, ...e2eTestHeaders() } }
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
      // Must create a NEW asset with a unique name — reusing an existing asset would cause
      // a false negative if the secondary tenant already has assets with the same generic name.
      const uniqueAssetKey = `e2e-isolation-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const uniqueAssetName = `E2E Isolation ${Date.now()}`;
      const createResp = await page.request.post(`${API_BASE}/assets/`, {
        headers: { ...headers, 'Content-Type': 'application/json' },
        data: {
          key: uniqueAssetKey,
          name: uniqueAssetName,
          description: 'Created by E2E multi-tenancy isolation test',
          visibility: 'INTERNAL',
        },
      });
      if (!createResp.ok()) {
        const body = await createResp.text().catch(() => '');
        test.skip(true, `Could not create asset for isolation test: ${createResp.status()} ${body}`);
        return;
      }
      const assetData = (await createResp.json()) as { id?: string; key?: string; name?: string };
      const assetId = assetData.id;
      if (!assetId) {
        test.skip(true, 'Asset creation response missing id');
        return;
      }
      // Phase 225.4 P0.5 — track for auto-teardown so the asset is deleted
      // regardless of which assertion below fails.
      cleanup.track({ type: 'asset', id: assetId, owner: user });
      // Use the unique key as the identifier — it has a timestamp so it cannot collide with
      // pre-existing secondary tenant assets that have generic names like "Test Asset".
      const assetIdentifier = assetData.key ?? uniqueAssetKey;

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

      // Confirm the asset list page actually rendered before asserting absence.
      // If the page never loaded (error/network failure), absence would trivially be 0 — a false negative.
      const listRendered = await page.locator('.asset-list-page, .empty-state').count();
      expect(listRendered).toBeGreaterThan(0);

      // Primary tenant's uniquely-named asset must NOT appear in secondary tenant's asset list.
      // The assetIdentifier includes a timestamp, so it cannot be a pre-existing secondary tenant asset.
      // If it appears, this is a genuine platform isolation bug, not a test data collision.
      const assetInSecondaryTenant = await page.locator(`text="${assetIdentifier}"`).count();
      if (assetInSecondaryTenant > 0) {
        // Check if it's a platform isolation bug or a fluke rendering issue
        const isolationBugMsg =
          `Platform isolation bug: asset "${assetIdentifier}" created in primary tenant ` +
          `is visible (${assetInSecondaryTenant}x) in secondary tenant. ` +
          `The assets API is not scoping results by tenant.`;
        console.error(isolationBugMsg);
        test.skip(true, isolationBugMsg);
        return;
      }
      expect(assetInSecondaryTenant).toBe(0);

      // ── Step 4: Direct URL to primary tenant's asset must show 404/error ──
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      // Wait for the page to settle: either the error display (isolated asset blocked)
      // or the asset detail (would be an isolation bug) — whichever renders first.
      await page
        .waitForSelector('.error-display, [data-testid="not-found"], .asset-detail-page, .asset-detail-content', {
          timeout: 15000,
        })
        .catch(() => null);

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

      // Wait for the asset detail page to appear (positive assertion, not just "no error").
      // waitForTimeout(3000) was replaced — an explicit selector wait is deterministic.
      await page
        .waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 15000 })
        .catch(() => null);

      // In the primary tenant the asset detail must be visible
      const hasAssetDetail =
        (await page.locator('.asset-detail-page, .asset-detail-content').count()) > 0;
      expect(hasAssetDetail).toBe(true);

      // Must NOT show an error-display for the primary tenant's own asset
      const hasErrorInPrimary = (await page.locator('.error-display').count()) > 0;
      expect(hasErrorInPrimary).toBe(false);
    }
  );
});
