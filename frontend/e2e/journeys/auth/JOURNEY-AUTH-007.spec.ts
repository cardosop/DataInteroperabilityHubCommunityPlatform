/**
 * E2E Test: JOURNEY-AUTH-007 — Tenant Switch (Isolation Guarantee)
 *
 * Journey: Authenticated user with membership in 2+ tenants exercises the
 * tenant-switch flow end-to-end and proves the **cross-tenant isolation
 * guarantee** at the API layer:
 *
 *   list-tenants → switch to A → create resource → verifyViaApi shows it
 *                → switch to B → verifyViaApiAbsent (the resource MUST 404
 *                                from tenant B's session)
 *                → switch back to A → verifyViaApi shows it again
 *
 * Priority: Critical
 * Use Case: UC-AUTH-007 (Tenant Switch — net-new in Phase 217.1.4 and
 *           critical-id-listed in docs/CRITICAL_UC_JOURNEY_IDS.yaml:50)
 * Tracked under: Phase 226.D2
 *
 * Why this is distinct from JOURNEY-AUTH-005:
 *   AUTH-005 covers UC-AUTH-005 (Invitation Accept) and the surface-level
 *   tenant-switch mechanics (dropdown opens, switcher renders, switch API
 *   responds 200, /auth/me/tenants/ shape is correct). It does NOT prove
 *   the security boundary — that resources created in tenant A become
 *   invisible from tenant B's session and visible again on switch-back.
 *   That isolation guarantee is the meat of UC-AUTH-007 and is the only
 *   thing that catches a tenant-leakage regression at the data layer.
 *
 * Why this spec uses verifyViaApiAbsent (404), not verifyViaApiForbidden
 * (403):
 *   Cross-tenant isolation is enforced by tenant-scoped querysets — a
 *   resource that doesn't belong to the active tenant simply doesn't
 *   exist from that tenant's perspective, so the response must be 404
 *   ("not found"), NOT 403 ("forbidden"). A 403 leaks the resource's
 *   existence and is itself a tenancy bug. See verifyViaApi.ts:191-218
 *   for the full rationale.
 *
 * All tests run against the real backend — no mocks/stubs.
 */

import { expect, test, type Page } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { e2eTestHeaders } from '../../fixtures/e2e-token';
import { verifyViaApi, verifyViaApiAbsent } from '../../fixtures/verifyViaApi';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

interface SwitchSetup {
  primary_tenant_id: string;
  primary_tenant_name: string;
  secondary_tenant_id: string;
  secondary_tenant_name: string;
}

/**
 * Provision (or reuse) a secondary tenant with the test user as a member,
 * via the backend's E2E-only test-helper. Returns null when the helper
 * is not available — typically because the deployment is missing the
 * `X-E2E-Token` shared secret (returns 404 by design when it can't
 * authenticate the request, matching the require_e2e_token decorator).
 *
 * The endpoint is gated on `ENVIRONMENT in (test, staging) or DEBUG`
 * AND the user being in the E2E_EMAILS allow-list AND the X-E2E-Token
 * header matching `settings.E2E_TEST_SECRET` via hmac.compare_digest —
 * see hub/apps/api/views.py:457-525 for the full guard chain.
 */
async function provisionSecondaryTenant(
  page: Page,
  accessToken: string,
): Promise<SwitchSetup | null> {
  const setupRes = await page.request.post(
    `${API_BASE}/test/ensure-e2e-tenant-switch-setup/`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...e2eTestHeaders(),
      },
    },
  );
  if (!setupRes.ok()) {
    return null;
  }
  return (await setupRes.json()) as SwitchSetup;
}

/**
 * Switch the active tenant via the canonical API path. Returns the new
 * `me` summary so the caller can assert the tenant_id rolled over.
 */
async function switchTenant(
  page: Page,
  accessToken: string,
  tenantId: string,
): Promise<{ tenant_id?: string; email?: string }> {
  const res = await page.request.post(`${API_BASE}/auth/switch-tenant/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    data: { tenant_id: tenantId },
  });
  expect(res.status(), `switch-tenant to ${tenantId} expected 200`).toBe(200);
  return (await res.json()) as { tenant_id?: string; email?: string };
}

test.describe('JOURNEY-AUTH-007: Tenant Switch — isolation guarantee', () => {
  test.setTimeout(180_000);

  test('list-tenants → switch → resource isolated → switch back → resource visible', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await expect(page.locator('.app-header')).toBeVisible({ timeout: 15_000 });

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) {
      throw new Error(
        'JOURNEY-AUTH-007: localStorage access_token is null after loginUser. ' +
          'The auth fixture should have established a session — investigate ' +
          'before retrying. Not skipping because this is a hard-fail signal.',
      );
    }

    // ─────────────────────────────────────────────────────────────────
    // Step 1 — Provision a secondary tenant (test-helper).
    //
    // If the helper is not available (X-E2E-Token mismatch or
    // ENVIRONMENT lockout), skip with a specific reason so the
    // skip-counter gate (Phase 226 PR 10) can fire if this recurs at
    // the configured threshold. We intentionally do NOT manufacture a
    // mocked second tenant — that would let a real tenant-leakage bug
    // pass undetected.
    // ─────────────────────────────────────────────────────────────────
    const setup = await provisionSecondaryTenant(page, accessToken);
    test.skip(
      setup === null,
      'ensure-e2e-tenant-switch-setup not reachable on this environment ' +
        '(check E2E_TEST_SECRET wired into the deployment + the user is in ' +
        'E2E_EMAILS allow-list). UC-AUTH-007 isolation guarantee cannot be ' +
        'asserted without a second tenant.',
    );
    if (setup === null) return;

    const { primary_tenant_id, primary_tenant_name, secondary_tenant_id, secondary_tenant_name } =
      setup;
    expect(primary_tenant_id).toBeTruthy();
    expect(secondary_tenant_id).toBeTruthy();
    expect(primary_tenant_id).not.toBe(secondary_tenant_id);
    console.log(
      `[AUTH-007] primary=${primary_tenant_name} (${primary_tenant_id.slice(0, 8)}) ` +
        `secondary=${secondary_tenant_name} (${secondary_tenant_id.slice(0, 8)})`,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 2 — /auth/me/tenants/ MUST list both tenants.
    //
    // This is the "list-tenants" leg of UC-AUTH-007. If the membership
    // service didn't register the secondary, the rest of the test is
    // moot — surface that loud and immediate.
    // ─────────────────────────────────────────────────────────────────
    await verifyViaApi(
      page,
      `/api/v1/auth/me/tenants/`,
      (body: Array<{ id: string }>) => {
        const ids = new Set(body.map((t) => t.id));
        return ids.has(primary_tenant_id) && ids.has(secondary_tenant_id);
      },
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 3 — Switch to PRIMARY (idempotent — sets the baseline).
    //
    // The user's session may already be on primary, but switching
    // explicitly removes any ambiguity from a previous test or a
    // multi-test run that left a different active tenant.
    // ─────────────────────────────────────────────────────────────────
    const meAfterPrimary = await switchTenant(page, accessToken, primary_tenant_id);
    expect(meAfterPrimary.tenant_id).toBe(primary_tenant_id);

    // ─────────────────────────────────────────────────────────────────
    // Step 4 — Create a resource in PRIMARY.
    //
    // We use an asset because /api/v1/assets/<id>/ is tenant-scoped at
    // the queryset level (see hub/apps/assets/views_optimized.py
    // get_queryset filtering on request.user.tenant). The resource is
    // the probe — it MUST be visible from primary and absent from
    // secondary.
    //
    // The asset key is unique per run so concurrent runs don't collide.
    // ─────────────────────────────────────────────────────────────────
    const assetKey = `auth-007-isolation-${Date.now()}`;
    const createRes = await page.request.post(`${API_BASE}/assets/`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        key: assetKey,
        name: 'AUTH-007 Isolation Probe',
        description: 'Tenant-isolation guarantee probe. Created in primary, must 404 in secondary.',
        domain: 'test',
        visibility: 'INTERNAL',
      },
    });
    expect(
      createRes.status(),
      `create asset in primary tenant expected 201; got ${createRes.status()}`,
    ).toBe(201);
    const created = (await createRes.json()) as { id: string; tenant?: string };
    const assetId = created.id;
    expect(assetId).toBeTruthy();

    // Channel-1 verification: GET from primary must succeed.
    await verifyViaApi(
      page,
      `/api/v1/assets/${assetId}/`,
      (body: { id: string; key: string }) => body.id === assetId && body.key === assetKey,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 5 — Switch to SECONDARY. The asset MUST 404.
    //
    // This is the security-boundary assertion. A 200 here means the
    // tenant-scoped queryset isn't filtering correctly — a real
    // tenancy leak that compromises every multi-tenant guarantee. A
    // 403 here is also a bug (it leaks the resource's existence by
    // returning a different code than for a genuinely-missing UUID).
    // verifyViaApiAbsent demands a 404 specifically.
    // ─────────────────────────────────────────────────────────────────
    const meAfterSecondary = await switchTenant(page, accessToken, secondary_tenant_id);
    expect(meAfterSecondary.tenant_id).toBe(secondary_tenant_id);

    await verifyViaApiAbsent(page, `/api/v1/assets/${assetId}/`);

    // ─────────────────────────────────────────────────────────────────
    // Step 6 — Switch back to PRIMARY. The asset MUST be visible again.
    //
    // Closes the loop: if we mis-attributed the asset to a global
    // queryset (the "always-visible" failure mode) the absent step
    // would have failed. If we mis-attributed it to the secondary
    // tenant, this step would fail. Together steps 5 + 6 prove the
    // tenant-id is the real partition key.
    // ─────────────────────────────────────────────────────────────────
    const meReturning = await switchTenant(page, accessToken, primary_tenant_id);
    expect(meReturning.tenant_id).toBe(primary_tenant_id);

    await verifyViaApi(
      page,
      `/api/v1/assets/${assetId}/`,
      (body: { id: string; key: string }) => body.id === assetId && body.key === assetKey,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 7 — Cleanup: retire the probe asset.
    //
    // Best-effort — staging will purge orphans on its scheduled
    // cleanup (226.E2 createdResources tracker is the longer-term
    // shape). If the retire fails the next run's unique key avoids
    // collision; we tolerate the failure here so the security
    // assertion above is the test's verdict, not the cleanup.
    // ─────────────────────────────────────────────────────────────────
    try {
      await page.request.patch(`${API_BASE}/assets/${assetId}/`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        data: { status: 'RETIRED' },
      });
    } catch {
      // intentional: cleanup failure must not invalidate the security
      // assertion above; the unique per-run key prevents subsequent
      // collisions, and 226.E2 will purge orphans.
    }
  });
});
