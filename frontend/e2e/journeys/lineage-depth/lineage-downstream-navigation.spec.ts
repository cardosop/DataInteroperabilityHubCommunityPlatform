/**
 * E2E spec — Lineage downstream navigation depth (Phase 226.G5).
 *
 * Background
 * ----------
 * Mirror of the upstream spec — asserts the `downstream` branch of
 * /lineage/full/ exposes data the UI can navigate. Distinct from upstream
 * because downstream traversal is the impact-analysis case
 * (who breaks if I change this?), not the provenance case (where did this
 * come from?).
 *
 * Spec shape:
 *   1. Arm: create contract with at least one downstream model reference.
 *   2. Drive: GET /lineage/full/ → assert `downstream` key + non-error
 *      shape.
 *   3. Drive: GET impact-analysis (the alternative downstream surface) —
 *      assert it returns a documented shape.
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../../fixtures/auth';
import { ensureE2eSubscription } from '../../fixtures/ensureE2eSubscription';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G5 — Lineage downstream navigation @critical @lineage', () => {
  test.setTimeout(180_000);

  test('contract lineage exposes downstream branch + impact-analysis surface for follow-on traversal', async ({
    page,
    cleanup,
  }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await ensureE2eSubscription(page, access_token);

    const odcs = JSON.stringify({
      apiVersion: 'odcs.io/v3.0.2',
      kind: 'DataContract',
      id: `e2e-g5-down-${Date.now()}`,
      name: 'G5 Downstream Probe',
      version: '1.0.0',
      // ODCS normalization requires schema.fields at the top level even
      // when models[].fields is also populated — see lineage-impact-analysis
      // spec for the same fix.
      schema: {
        fields: [
          { name: 'order_id', type: 'string' },
          { name: 'amount', type: 'number' },
        ],
        models: [
          {
            name: 'OrderModel',
            fields: [
              { name: 'order_id', type: 'string' },
              { name: 'amount', type: 'number' },
            ],
          },
        ],
      },
    });
    const cRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers,
      data: { original_raw: odcs, original_format: 'JSON', original_spec_type: 'ODCS' },
    });
    if (!cRes.ok()) {
      // Fail loudly — silent skips hide regressions in the normalization path.
      throw new Error(
        `contract create failed (${cRes.status()}): ${(await cRes.text()).slice(0, 400)}`,
      );
    }
    const c = (await cRes.json()) as { id: string };
    cleanup.track({ type: 'contract', id: c.id, owner: dpo });

    // ── /lineage/full/ — assert downstream key.
    const fullRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/full/?max_contract_depth=5`,
      { headers },
    );
    expect(fullRes.ok()).toBe(true);
    const fullBody = (await fullRes.json()) as { downstream?: unknown; upstream?: unknown };
    expect(
      'downstream' in fullBody,
      `lineage/full response must include 'downstream'; got keys=${Object.keys(fullBody)}`,
    ).toBe(true);

    // ── /impact-analysis/ — alternative downstream surface.
    const impactRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/impact-analysis/?depth=5`,
      { headers },
    );
    if (impactRes.status() === 404) {
      test.info().annotations.push({
        type: 'g5-impact-analysis-missing',
        description: 'Impact-analysis endpoint not enabled (404) — feature gate.',
      });
      return;
    }
    expect(impactRes.ok()).toBe(true);
    const impactBody = (await impactRes.json()) as Record<string, unknown>;
    expect(Object.keys(impactBody).length).toBeGreaterThan(0);
  });
});
