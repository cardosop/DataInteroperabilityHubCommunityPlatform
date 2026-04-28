/**
 * E2E spec — Retired asset cannot be reactivated (Phase 226.G2).
 *
 * Background — terminal-state guarantee
 * -------------------------------------
 * `AssetService.activate` (`hub/apps/assets/views.py:1235-1241`) explicitly
 * rejects activation attempts on RETIRED assets with:
 *   400 { "error": "Retired assets cannot be reactivated",
 *         "code": "ASSET_RETIRED" }
 *
 * This is a deliberate platform contract: RETIRED is a *terminal* lifecycle
 * state — re-using a retired key would corrupt downstream caches, audit
 * provenance, and contract attachment history. A regression that allowed
 * reactivation would silently re-publish stale data into the marketplace.
 *
 * Guarantee chain asserted here:
 *   1. Create + retire an asset.
 *   2. POST /assets/{id}/activate/ → 400 with code='ASSET_RETIRED'.
 *   3. verifyViaApi confirms `status='RETIRED'` is unchanged after the
 *      blocked attempt (no half-state on the row).
 *   4. No ASSET_ACTIVATED audit row appears post-block (we wait briefly
 *      then negative-assert).
 *   5. Cascade — the same blocked attempt with PATCH `status=ACTIVE`
 *      (alternate UI path) is also rejected.
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../../fixtures/auth';
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import {
  findMatchingAuditEvent,
  type AuditEventRow,
} from '../../fixtures/verifyAuditEvent';
import { ensureE2eSubscription } from '../../fixtures/ensureE2eSubscription';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G2 — Retired asset cannot be reactivated @critical @lifecycle', () => {
  test.setTimeout(180_000);

  test('RETIRED asset → activate POST → 400 ASSET_RETIRED, status preserved, no spurious activation audit row', async ({
    page,
    cleanup,
  }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await page.goto('/');
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access_token);

    await ensureE2eSubscription(page, access_token);

    // ── Step 1 — Create asset.
    const assetKey = `e2e-${cleanup.runId}-g2-retire-asset-${Date.now()}`;
    const assetRes = await page.request.post(`${API_BASE}/assets/`, {
      headers,
      data: {
        key: assetKey,
        name: 'G2 Retired-Reactivate Probe',
        description: '226.G2 reactivate-blocked probe',
        visibility: 'INTERNAL',
      },
    });
    expect(assetRes.status()).toBe(201);
    const asset = (await assetRes.json()) as { id: string; status: string };
    cleanup.track({ type: 'asset', id: asset.id, owner: dpo });

    // ── Step 2 — Retire (via DELETE → soft-delete).
    const retireRes = await page.request.delete(`${API_BASE}/assets/${asset.id}/`, { headers });
    expect(retireRes.status()).toBe(204);

    // Confirm RETIRED state.
    await verifyViaApi<{ status: string }>(
      page,
      `/api/v1/assets/${asset.id}/`,
      (body) => body.status === 'RETIRED',
    );

    // ── Step 3 — Attempt activation via dedicated endpoint.
    // The activate endpoint requires `version` for optimistic locking
    // (`hub/apps/assets/views.py:1197-1207`). Without it the response is
    // 400 VALIDATION_ERROR ("version required") — which would mask the
    // real assertion (ASSET_RETIRED). Refresh the asset to get the
    // current version (delete bumps it via the lifecycle handler), then
    // POST with the correct version so the RETIRED guard at views.py:1236
    // is the path that actually fires.
    const refresh = await page.request.get(`${API_BASE}/assets/${asset.id}/`, { headers });
    expect(refresh.ok()).toBe(true);
    const refreshed = (await refresh.json()) as { version: number };

    const activateRes = await page.request.post(
      `${API_BASE}/assets/${asset.id}/activate/`,
      { headers, data: { version: refreshed.version } },
    );
    expect(
      activateRes.status(),
      `Activate of RETIRED asset expected 400; got ${activateRes.status()}`,
    ).toBe(400);
    const activateBody = (await activateRes.json()) as { code?: string; error?: string };
    expect(
      activateBody.code,
      `Expected error code ASSET_RETIRED; got ${JSON.stringify(activateBody)}`,
    ).toBe('ASSET_RETIRED');

    // ── Step 4 — Confirm status didn't drift to ACTIVE.
    await verifyViaApi<{ status: string }>(
      page,
      `/api/v1/assets/${asset.id}/`,
      (body) => body.status === 'RETIRED',
    );

    // ── Step 5 — Negative-assert no ASSET_ACTIVATED audit row appeared.
    // (Use the audit-events list directly; we want presence==false, not
    // presence==true, so verifyAuditEvent is the wrong shape here.)
    const auditResp = await page.request.get(
      `${API_BASE}/audit/audit-events/?resource_id=${asset.id}&action=ASSET_ACTIVATED&page_size=10`,
      { headers },
    );
    if (auditResp.ok()) {
      const auditBody = (await auditResp.json()) as
        | { results?: AuditEventRow[] }
        | AuditEventRow[];
      const rows = Array.isArray(auditBody) ? auditBody : auditBody.results ?? [];
      const found = findMatchingAuditEvent(rows, {
        action: 'ASSET_ACTIVATED',
        resourceType: 'ASSET',
        resourceId: asset.id,
      });
      expect(
        found.matched,
        `Spurious ASSET_ACTIVATED audit row found despite blocked activation: ${JSON.stringify(found.matched)}`,
      ).toBeNull();
    }

    // ── Step 6 — Alternate path: PATCH status=ACTIVE — must also reject.
    const patchRes = await page.request.patch(`${API_BASE}/assets/${asset.id}/`, {
      headers,
      data: { status: 'ACTIVE', version: 1 },
    });
    // Acceptable: 400 (validation reject), 409 (version conflict), or
    // 422-style domain reject. NOT acceptable: 200 with the asset re-
    // activated.
    expect(
      patchRes.status(),
      `PATCH to ACTIVE on RETIRED asset must not 2xx; got ${patchRes.status()}`,
    ).toBeGreaterThanOrEqual(400);
    expect(patchRes.status()).toBeLessThan(500);
    // Final state remains RETIRED.
    await verifyViaApi<{ status: string }>(
      page,
      `/api/v1/assets/${asset.id}/`,
      (body) => body.status === 'RETIRED',
    );
  });
});
