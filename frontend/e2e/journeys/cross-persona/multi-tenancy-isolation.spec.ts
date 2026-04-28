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
      // contentSelector must be an element inside .app-main, [data-testid="app-main"]; [data-testid="home-page"] is
      // rendered by HomePage.tsx directly inside .app-main, [data-testid="app-main"] (not .app-sidebar/.app-header, [data-testid="app-header"]
      // which are siblings of .app-main, [data-testid="app-main"] and would never resolve).
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"]',
      });

      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        // No token after a successful login is an environment problem
        // (cookie/storage policy), not a "feature gated" condition. Surface it
        // as a hard failure with the diagnostic instead of skipping silently.
        throw new Error(
          'No access_token in localStorage after loginAndNavigateToRoute. ' +
            'Cookie/storage policy may be blocking persistence — check the ' +
            'browser context and login flow.',
        );
      }
      const headers = { Authorization: `Bearer ${accessToken}` };

      // Ensure the user has a secondary tenant.
      //
      // The endpoint at `/test/ensure-e2e-tenant-switch-setup/` is gated by
      // (a) `ENVIRONMENT in ('test', 'staging') or DEBUG`
      //     (hub/apps/api/views.py:480 — staging IS supported), AND
      // (b) the test user's email being in `E2E_EMAILS`, AND
      // (c) a valid X-E2E-Token header matching `settings.E2E_TEST_SECRET`
      //     (the @require_e2e_token decorator at hub/apps/api/decorators.py).
      //
      // A 404 here is therefore NOT "feature unavailable" — it is one of three
      // misconfigurations that we want to surface, not skip silently:
      //   * `ENVIRONMENT` env var on the API pod is set to something other
      //     than `test` / `staging` (e.g. accidentally `production`)
      //   * test user's email isn't in the `E2E_EMAILS` allowlist
      //   * `E2E_TEST_SECRET` env var on the test runner doesn't match the
      //     value `ExternalSecrets` injected into the API pod
      // The previous silent-skip masked all three cases; the run would go
      // green with multi-tenancy isolation untested for weeks. Hard-fail with
      // the response body so the next run is one-shot diagnosable.
      const setupRes = await page.request.post(
        `${API_BASE}/test/ensure-e2e-tenant-switch-setup/`,
        { headers: { ...headers, ...e2eTestHeaders() } }
      );
      if (!setupRes.ok()) {
        const status = setupRes.status();
        const body = await setupRes.text().catch(() => '');
        const tokenLen = (process.env.E2E_TEST_SECRET ?? '').length;
        throw new Error(
          `ensure-e2e-tenant-switch-setup returned ${status}. ` +
            `Body (first 300): ${body.slice(0, 300)}. ` +
            `User email: ${user.email}. ` +
            `E2E_TEST_SECRET present in test-runner env: ${tokenLen > 0} (length=${tokenLen}). ` +
            `Remediation: (1) confirm staging API pod has ENVIRONMENT=staging ` +
            `and E2E_TEST_SECRET injected via ExternalSecrets, ` +
            `(2) confirm \`${user.email}\` is in the backend E2E_EMAILS allowlist ` +
            `(hub/apps/api/views.py), ` +
            `(3) confirm the test runner's E2E_TEST_SECRET env var matches ` +
            `the staging Secrets Manager value at staging/hub/e2e.`,
        );
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
        // intentional: tolerates non-text / streaming response body when building a diagnostic message.
        const body = await createResp.text().catch(() => '');
        // Asset creation is the test's data setup, not a feature gate. A 4xx/5xx
        // here is a real failure (auth invalid, plan-cap reached, validation error)
        // that must be diagnosed — silently skipping would let billing or auth
        // regressions go undetected on this critical-path tenant-isolation test.
        throw new Error(
          `Asset creation for isolation test failed with HTTP ${createResp.status()}. ` +
            `Body: ${body.slice(0, 300)}. The multi-tenancy isolation test cannot ` +
            `proceed without a primary-tenant asset; do not silently skip.`,
        );
      }
      const assetData = (await createResp.json()) as { id?: string; key?: string; name?: string };
      const assetId = assetData.id;
      if (!assetId) {
        // 2xx without an id is a backend-contract violation — surface it.
        throw new Error(
          `Asset creation returned ${createResp.status()} but the response body ` +
            `had no \`id\` field. Response: ${JSON.stringify(assetData).slice(0, 300)}. ` +
            `This is a backend-contract regression and must not be silently skipped.`,
        );
      }
      // Phase 225.4 P0.5 — track for auto-teardown so the asset is deleted
      // regardless of which assertion below fails.
      cleanup.track({ type: 'asset', id: assetId, owner: user });
      // Use the unique key as the identifier — it has a timestamp so it cannot collide with
      // pre-existing secondary tenant assets that have generic names like "Test Asset".
      const assetIdentifier = assetData.key ?? uniqueAssetKey;

      // ── Step 2: Switch to secondary tenant via UI dropdown ────────────────
      await page.goto('/');
      await page.waitForSelector('.app-sidebar, .app-header, [data-testid="app-header"]', { timeout: 15000 });

      const { newTenantName } = await switchTenantViaUI(page, setup.secondary_tenant_name);
      expect(newTenantName).toContain(setup.secondary_tenant_name);

      // ── Step 3: Navigate to assets in secondary tenant ────────────────────
      await page.goto('/assets');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]', {
        timeout: 20000,
      });

      // Confirm the asset list page actually rendered before asserting absence.
      // If the page never loaded (error/network failure), absence would trivially be 0 — a false negative.
      const listRendered = await page.locator('.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"]').count();
      expect(listRendered).toBeGreaterThan(0);

      // Primary tenant's uniquely-named asset must NOT appear in secondary tenant's asset list.
      // The assetIdentifier includes a timestamp, so it cannot be a pre-existing secondary tenant asset.
      // If it appears, this is a genuine platform isolation bug — a SECURITY REGRESSION
      // that must fail loudly, NOT a "skip" condition. The previous code converted this into
      // test.skip(...) which made tenant-isolation breakage report as green; that defeats the
      // entire purpose of a multi-tenancy guarantee test.
      const assetInSecondaryTenant = await page.locator(`text="${assetIdentifier}"`).count();
      expect(
        assetInSecondaryTenant,
        `SECURITY REGRESSION — TENANT ISOLATION BREACH: asset "${assetIdentifier}" ` +
          `created in primary tenant ${setup.primary_tenant_name} ` +
          `(${setup.primary_tenant_id}) is visible (${assetInSecondaryTenant}x) ` +
          `in secondary tenant ${setup.secondary_tenant_name} ` +
          `(${setup.secondary_tenant_id}). The assets list API is not scoping ` +
          `results by tenant. This is the exact failure mode this test exists to ` +
          `catch — fix the tenant scoping in hub/apps/assets/views.py before merging.`,
      ).toBe(0);

      // ── Step 4: Direct URL to primary tenant's asset must show 404/error ──
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      // Wait for the page to settle: either the error display (isolated asset blocked)
      // or the asset detail (would be an isolation bug) — whichever renders first.
      // intentional: probes optional UI via a multi-line waitForSelector chain — same shape as waitFor; absence is a legitimate state handled by the caller's branch below.
      await page
        .waitForSelector('.error-display, [data-testid="error-display"], [data-testid="not-found"], .asset-detail-page, [data-testid="asset-detail-page"], .asset-detail-content', {
          timeout: 15000,
        })
        .catch(() => null);

      const url = page.url();
      const hasErrorForIsolatedAsset =
        // Shows a 404/error boundary
        (await page.locator('.error-display, [data-testid="error-display"], [data-testid="not-found"], .not-found-page').count()) > 0 ||
        // Redirected away from the asset URL (e.g., back to list)
        (!url.includes(assetId)) ||
        // URL changed to 404
        url.includes('/404');
      expect(hasErrorForIsolatedAsset).toBe(true);

      // ── Step 5: Switch back to primary tenant — asset IS visible ──────────
      await page.goto('/');
      await page.waitForSelector('.app-sidebar, .app-header, [data-testid="app-header"]', { timeout: 15000 });

      const { newTenantName: restoredName } = await switchTenantViaUI(
        page,
        setup.primary_tenant_name
      );
      expect(restoredName).toContain(setup.primary_tenant_name);

      // Navigate to the asset directly — should load without error.
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');

      // In the primary tenant the asset detail MUST be visible.
      //
      // Use Playwright's auto-retrying `expect(locator).toBeVisible(...)`
      // matcher rather than a fire-and-forget `waitForSelector + count()` pair.
      // Three reasons:
      //
      //   1. After `switchTenantViaUI`, React-Query invalidates per-tenant
      //      caches and the asset detail must be re-fetched with the new auth
      //      context. On a busy staging the round-trip occasionally exceeds
      //      the previous 15 s ceiling; the auto-retry semantics absorb that
      //      tail latency without changing the contract.
      //   2. `count() > 0` is a snapshot of "does the selector exist *right
      //      now*"; a negative result on a slow render gives a misleading
      //      `Expected: true / Received: false` with no info on what was on
      //      the page. `toBeVisible` waits for the element to actually paint
      //      AND emits a clean diagnostic on failure ("element not visible
      //      after Nms; current URL: …").
      //   3. The previous code used `waitForSelector(...).catch(() => null)`
      //      (a silent timeout swallow) followed by an `expect`. That meant
      //      a slow render and a real isolation regression both surfaced as
      //      the same generic `false === true` failure — the new shape pins
      //      the actual state.
      const detailLocator = page.locator(
        '.asset-detail-content, .asset-detail-page, [data-testid="asset-detail-page"]',
      );
      await expect(detailLocator.first()).toBeVisible({ timeout: 30_000 });

      // Must NOT show an error-display for the primary tenant's own asset.
      const errorLocator = page.locator(
        '.error-display, [data-testid="error-display"]',
      );
      await expect(errorLocator.first()).toBeHidden({ timeout: 5_000 });
    }
  );
});
