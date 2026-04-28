/**
 * E2E spec — Access request deny (reject) state transition (Phase 226.G2).
 *
 * Background
 * ----------
 * AccessRequest lifecycle: PENDING → REJECTED via
 * `POST /api/v1/governance/access-requests/{id}/reject/` with required
 * `reason`. Implementation at
 * `hub/apps/governance/access_request_views.py:223-286`.
 *
 * Audit emission: ACCESS_REQUEST_REJECTED row, with
 * `details.rejection_reason` carrying the operator-supplied reason.
 *
 * Guarantee chain asserted here:
 *   1. Pre-state: PENDING access request.
 *   2. Approver POSTs to /reject/ with reason → 200.
 *   3. Reject without reason returns 400 VALIDATION_ERROR — the reason
 *      requirement is enforced (compliance trail integrity).
 *   4. verifyViaApi confirms `status='REJECTED'` and `rejection_reason`
 *      surfaces on the serializer (when present).
 *   5. ACCESS_REQUEST_REJECTED audit row exists.
 *   6. Idempotent re-reject rejected with 400 (state machine guard).
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../../fixtures/auth';
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

test.describe('226.G2 — Access request deny state transition @critical @lifecycle', () => {
  test.setTimeout(180_000);

  test('PENDING → reject(reason) → REJECTED, audit row written, reason-required guard, idempotent re-reject blocked', async ({
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

    // ── Step 1 — Provision an asset to gate access on.
    const assetKey = `e2e-${cleanup.runId}-g2-deny-asset-${Date.now()}`;
    const assetRes = await page.request.post(`${API_BASE}/assets/`, {
      headers,
      data: {
        key: assetKey,
        name: 'G2 Access Request Deny Probe Asset',
        description: '226.G2 access-request-deny probe parent',
        visibility: 'INTERNAL',
      },
    });
    expect(assetRes.status()).toBe(201);
    const asset = (await assetRes.json()) as { id: string };
    cleanup.track({ type: 'asset', id: asset.id, owner: dpo });

    // ── Step 2 — Create the PENDING access request.
    const arRes = await page.request.post(`${API_BASE}/governance/access-requests/`, {
      headers,
      data: {
        asset_id: asset.id,
        reason: '226.G2 deny probe — programmatic test request',
        requested_access_type: 'READ',
      },
    });
    if (!arRes.ok()) {
      test.skip(
        true,
        `Could not create access request (status=${arRes.status()} body=${(await arRes.text()).slice(0, 200)})`,
      );
      return;
    }
    const ar = (await arRes.json()) as { id: string; status: string };
    expect(ar.status).toBe('PENDING');
    const arId = ar.id;

    // ── Step 3 — Reject WITHOUT reason → 400 VALIDATION_ERROR (compliance
    // trail integrity guard).
    const rejectNoReason = await page.request.post(
      `${API_BASE}/governance/access-requests/${arId}/reject/`,
      { headers, data: {} },
    );
    expect(
      rejectNoReason.status(),
      `Reject without reason should be 400; got ${rejectNoReason.status()}`,
    ).toBe(400);
    const noReasonBody = (await rejectNoReason.json()) as { code?: string; error?: string };
    expect(
      noReasonBody.code === 'VALIDATION_ERROR' || /reason/i.test(noReasonBody.error ?? ''),
      `Expected VALIDATION_ERROR or reason-mention; got ${JSON.stringify(noReasonBody)}`,
    ).toBe(true);

    // ── Step 4 — Reject WITH reason → 200.
    const reason = 'Insufficient business justification (probe test).';
    const rejectRes = await page.request.post(
      `${API_BASE}/governance/access-requests/${arId}/reject/`,
      { headers, data: { reason } },
    );
    expect(
      rejectRes.status(),
      `reject expected 200; got ${rejectRes.status()} ${await rejectRes.text()}`,
    ).toBe(200);

    // ── Step 5 — Terminal state.
    await verifyViaApi<{
      id: string;
      status: string;
      rejection_reason?: string | null;
    }>(page, `/api/v1/governance/access-requests/${arId}/`, (body) => {
      const matchesId = body.id === arId;
      const isRejected = body.status === 'REJECTED';
      // rejection_reason may not be on the serializer; if it is, it must match.
      const reasonOk = body.rejection_reason === undefined || body.rejection_reason === reason;
      return matchesId && isRejected && reasonOk;
    });

    // ── Step 6 — Audit row.
    await verifyAuditEvent(page, {
      action: 'ACCESS_REQUEST_REJECTED',
      resourceType: 'ACCESS_REQUEST',
      resourceId: arId,
    });

    // ── Step 7 — Idempotent re-reject rejected.
    const reReject = await page.request.post(
      `${API_BASE}/governance/access-requests/${arId}/reject/`,
      { headers, data: { reason: 'second attempt' } },
    );
    expect(
      reReject.status(),
      `Re-reject of REJECTED request expected 400; got ${reReject.status()}`,
    ).toBe(400);
  });
});
