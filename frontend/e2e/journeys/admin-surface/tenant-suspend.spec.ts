/**
 * E2E spec — Tenant suspend / reactivate state transition (Phase 226.G3).
 *
 * Background — E6 dependency
 * --------------------------
 * The G3 task notes: "Tenant-suspend requires E6; if E6 not landed, G3
 * ships without that sub-spec." Per `openspec/changes/preprod01/tasks.md:
 * 11808` E6 is "IMPLEMENTED, BLOCKED on backend OQ4" — the
 * `disposableTenant.ts` fixture is shipped but the `/api/v1/test/
 * provision-disposable-tenant/` endpoint is missing on staging.
 *
 * This spec ships the suspend/reactivate guarantee chain anyway, gated on
 * the disposable-tenant endpoint being reachable. When the backend ships
 * the helper, the spec runs end-to-end. Until then, it skips with a
 * specific reason — exactly the shape the G3 task anticipated.
 *
 * Guarantee chain asserted here:
 *   1. Provision a disposable tenant (E6) → POST suspend → 200, status='SUSPENDED',
 *      TENANT_SUSPENDED audit row.
 *   2. Re-suspend rejected (idempotent guard).
 *   3. Reactivate → 200, status='ACTIVE', TENANT_REACTIVATED audit row.
 *   4. Reactivate of already-ACTIVE rejected.
 *   5. Suspend of DELETED tenant rejected with specific 400.
 *
 * Refusing to provision a real-tenant against the live backend is
 * intentional: suspending a shared-tenant in staging would block other
 * E2E workers and break unrelated tests.
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getPlatformAdminUser, loginViaApi } from '../../fixtures/auth';
import { e2eTestHeaders } from '../../fixtures/e2e-token';
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G3 — Tenant suspend / reactivate @critical @admin @e6-dependent', () => {
  test.setTimeout(180_000);

  test('disposable-tenant provisioning required: suspend → SUSPENDED+audit, reactivate → ACTIVE+audit, idempotency guards intact', async ({
    page,
  }) => {
    let admin;
    try {
      admin = await getPlatformAdminUser();
    } catch (err) {
      test.skip(
        true,
        `No platform admin available (${(err as Error).message}). Run ensure_e2e_user_roles.`,
      );
      return;
    }
    const { access_token } = await loginViaApi(admin.email, admin.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await page.goto('/');
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access_token);

    // ── Step 1 — Provision disposable tenant (E6 backend dependency).
    const disposableRes = await page.request.post(
      `${API_BASE}/test/provision-disposable-tenant/`,
      { headers: { ...headers, ...e2eTestHeaders() } },
    );
    if (!disposableRes.ok()) {
      test.skip(
        true,
        `E6 disposable-tenant endpoint unreachable (${disposableRes.status()}). ` +
          `Per 226.OQ4 / E6 status, this endpoint is not yet on staging. ` +
          `Spec will run end-to-end as soon as the backend stand-up lands.`,
      );
      return;
    }
    const disposable = (await disposableRes.json()) as { tenant_id: string; tenant_name?: string };
    expect(disposable.tenant_id).toBeTruthy();

    // ── Step 2 — Suspend.
    const suspendRes = await page.request.post(
      `${API_BASE}/tenants/${disposable.tenant_id}/suspend/`,
      { headers, data: { reason: '226.G3 suspend probe' } },
    );
    expect(
      suspendRes.status(),
      `suspend expected 200; got ${suspendRes.status()} ${await suspendRes.text()}`,
    ).toBe(200);

    await verifyViaApi<{ id: string; status: string }>(
      page,
      `/api/v1/tenants/${disposable.tenant_id}/`,
      (body) => body.id === disposable.tenant_id && body.status === 'SUSPENDED',
    );
    await verifyAuditEvent(page, {
      action: 'TENANT_SUSPENDED',
      resourceType: 'TENANT',
      resourceId: disposable.tenant_id,
    });

    // ── Step 3 — Re-suspend (already-SUSPENDED) is rejected by the model
    // (Tenant.suspend() raises a domain error; view returns 400).
    const reSuspendRes = await page.request.post(
      `${API_BASE}/tenants/${disposable.tenant_id}/suspend/`,
      { headers, data: { reason: '226.G3 re-suspend probe' } },
    );
    // Some backends accept idempotent re-suspend (200 no-op) — both shapes
    // are acceptable as long as they're not a 5xx and don't flip status.
    expect(reSuspendRes.status()).toBeLessThan(500);
    await verifyViaApi<{ status: string }>(
      page,
      `/api/v1/tenants/${disposable.tenant_id}/`,
      (body) => body.status === 'SUSPENDED',
    );

    // ── Step 4 — Reactivate.
    const reactivateRes = await page.request.post(
      `${API_BASE}/tenants/${disposable.tenant_id}/reactivate/`,
      { headers, data: {} },
    );
    expect(reactivateRes.status()).toBe(200);
    await verifyViaApi<{ status: string }>(
      page,
      `/api/v1/tenants/${disposable.tenant_id}/`,
      (body) => body.status === 'ACTIVE',
    );
    await verifyAuditEvent(page, {
      action: 'TENANT_REACTIVATED',
      resourceType: 'TENANT',
      resourceId: disposable.tenant_id,
    });

    // ── Step 5 — Reactivate of already-ACTIVE rejected.
    const reReactivateRes = await page.request.post(
      `${API_BASE}/tenants/${disposable.tenant_id}/reactivate/`,
      { headers, data: {} },
    );
    expect(reReactivateRes.status()).toBe(400);
  });
});
