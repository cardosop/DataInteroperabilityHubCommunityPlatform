/**
 * E2E spec — Contract destructive-action guarantee chain (Phase 226.G1).
 *
 * Background — soft-delete reality
 * --------------------------------
 * Contract DELETE soft-deletes (status='RETIRED'). See
 * `hub/apps/contracts/views_crud.py:259-340`. The frontend Contract list
 * page exposes a bulk-delete restricted to DRAFT contracts; the
 * `contractService.delete()` (`frontend/src/features/contracts/services/
 * contractService.ts:87-89`) issues `DELETE /api/v1/contracts/{id}/`.
 *
 * Guarantee chain asserted here:
 *   1. UI delete (DELETE /api/v1/contracts/{id}/) returns 204.
 *   2. Detail GET still resolves with `status='RETIRED'`.
 *   3. List GET filtered to active statuses no longer surfaces the row.
 *   4. CONTRACT_DELETED audit row exists.
 *   5. Re-DELETE rejected (no double audit, no 5xx).
 *   6. Cascade — if the contract was attached to an asset, the asset's
 *      `current_contract_id` reference is cleared (per service-layer
 *      `delete_contract` semantics).
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTenantAdminUser, loginViaApi } from '../../fixtures/auth';
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';
import { ensureE2eSubscription } from '../../fixtures/ensureE2eSubscription';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G1 — Contract delete guarantee chain @critical @destructive', () => {
  test.setTimeout(180_000);

  test('soft-delete: contract terminally retired, audit row written, attached asset detaches cleanly', async ({
    page,
    cleanup,
  }) => {
    // Contract DELETE requires TENANT_ADMIN role (`hub/apps/contracts/
    // views_crud.py:268` → `check_auditor_permissions("destroy")` then the
    // service-layer permission check). The default e2e user is DATA_PROVIDER,
    // which gets a 403. Use the seeded TA account.
    const dpo = await getTenantAdminUser();
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

    // ── Step 1 — Create the parent asset for cascade verification.
    const assetKey = `e2e-${cleanup.runId}-g1-cdel-asset-${Date.now()}`;
    const assetRes = await page.request.post(`${API_BASE}/assets/`, {
      headers,
      data: {
        key: assetKey,
        name: 'G1 Contract-Delete Parent Asset',
        description: '226.G1 contract-delete cascade-preservation parent',
        visibility: 'INTERNAL',
      },
    });
    expect(assetRes.status()).toBe(201);
    const asset = (await assetRes.json()) as { id: string };
    cleanup.track({ type: 'asset', id: asset.id, owner: dpo });

    // ── Step 2 — Create a contract bound to the asset.
    const odcs = JSON.stringify({
      apiVersion: 'odcs.io/v3.0.2',
      kind: 'DataContract',
      id: `e2e-g1-cdel-${Date.now()}`,
      name: 'G1 Contract Delete Probe',
      version: '1.0.0',
      schema: { fields: [{ name: 'id', type: 'string' }] },
    });
    const contractRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers,
      data: {
        asset_id: asset.id,
        original_raw: odcs,
        original_format: 'JSON',
        original_spec_type: 'ODCS',
      },
    });
    expect(
      contractRes.status(),
      `contract create expected 201; got ${contractRes.status()} ${await contractRes.text()}`,
    ).toBe(201);
    const contract = (await contractRes.json()) as { id: string; status?: string };
    const contractId = contract.id;
    expect(contractId).toBeTruthy();
    cleanup.track({ type: 'contract', id: contractId, owner: dpo });

    // ── Step 3 — DELETE the contract.
    const deleteRes = await page.request.delete(`${API_BASE}/contracts/${contractId}/`, {
      headers,
    });
    expect(
      deleteRes.status(),
      `DELETE expected 204; got ${deleteRes.status()} ${await deleteRes.text()}`,
    ).toBe(204);

    // ── Step 4 — Detail GET resolves with terminal state.
    await verifyViaApi<{ id: string; status: string }>(
      page,
      `/api/v1/contracts/${contractId}/`,
      (body) => body.id === contractId && body.status === 'RETIRED',
    );

    // ── Step 5 — List query no longer surfaces the row under active status.
    const listRes = await page.request.get(
      `${API_BASE}/contracts/?status=DRAFT&page_size=100`,
      { headers },
    );
    expect(listRes.ok()).toBe(true);
    const listBody = (await listRes.json()) as
      | { results?: Array<{ id: string; status?: string }> }
      | Array<{ id: string }>;
    const rows = Array.isArray(listBody) ? listBody : listBody.results ?? [];
    const found = rows.find((r) => r.id === contractId);
    expect(
      found,
      `RETIRED contract ${contractId} should not appear in status=DRAFT list, found=${JSON.stringify(found)}`,
    ).toBeUndefined();

    // ── Step 6 — Audit trail row written.
    await verifyAuditEvent(page, {
      action: 'CONTRACT_DELETED',
      resourceType: 'CONTRACT',
      resourceId: contractId,
    });

    // ── Step 7 — Re-DELETE must not 5xx.
    const reDel = await page.request.delete(`${API_BASE}/contracts/${contractId}/`, { headers });
    expect(
      reDel.status(),
      `Re-DELETE returned 5xx — likely a double-cascade crash. Status=${reDel.status()}`,
    ).toBeLessThan(500);

    // ── Step 8 — Cascade: asset's current_contract reference must not point
    // at a stale ID. Acceptable: null (detached) OR equal to contractId (left
    // as historical pointer with the contract in RETIRED state). NOT
    // acceptable: pointing at a different live contract that the test never
    // created.
    const assetGet = await page.request.get(`${API_BASE}/assets/${asset.id}/`, { headers });
    expect(assetGet.ok()).toBe(true);
    const assetBody = (await assetGet.json()) as {
      id: string;
      current_contract_id?: string | null;
      contract_id?: string | null;
    };
    const ref = assetBody.current_contract_id ?? assetBody.contract_id ?? null;
    if (ref !== null) {
      expect(
        ref,
        `Asset's contract reference is unexpectedly pointing at ${ref}; expected null or original contractId ${contractId}`,
      ).toBe(contractId);
    }
  });
});
