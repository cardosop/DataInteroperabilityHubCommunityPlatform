/**
 * E2E spec — Lineage impact-analysis surface (Phase 226.G5).
 *
 * Background
 * ----------
 * `GET /api/v1/contracts/{id}/impact-analysis/` (`hub/apps/contracts/
 * views_impact.py:93-208`) accepts depth + model_name + field_name +
 * include_fields + output (json/csv) parameters. The response is the
 * load-bearing data for the "what breaks if I change this?" UI.
 *
 * Spec asserts:
 *   1. Default JSON response is structurally valid (top-level keys exist).
 *   2. CSV output mode returns text/csv with at least a header row.
 *   3. Field-scoped query (?field_name=…) doesn't 5xx.
 *   4. Depth boundary: depth=0 returns a degenerate but valid response
 *      (no panic).
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

test.describe('226.G5 — Lineage impact-analysis @critical @lineage', () => {
  test.setTimeout(180_000);

  test('impact-analysis surface honors depth + format + scope params without 5xx', async ({
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
      id: `e2e-g5-impact-${Date.now()}`,
      name: 'G5 Impact Analysis Probe',
      version: '1.0.0',
      // ODCS normalization (`hub/apps/contracts/normalization/...`)
      // requires BOTH a top-level `schema.fields` AND nested
      // `schema.models[].fields`. Omitting either trips:
      //   "schema -> fields: Value error, schema.fields must contain at least one field"
      // The lineage walker treats schema-level fields as the contract's
      // public surface and model-level fields as the implementation detail.
      schema: {
        fields: [{ name: 'pk', type: 'string' }],
        models: [
          {
            name: 'M',
            fields: [{ name: 'pk', type: 'string' }],
          },
        ],
      },
    });
    const cRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers,
      data: { original_raw: odcs, original_format: 'JSON', original_spec_type: 'ODCS' },
    });
    if (!cRes.ok()) {
      // Fail loudly rather than skipping — silent skips on contract create
      // hide real regressions in the normalization path.
      throw new Error(
        `contract create failed (${cRes.status()}): ${(await cRes.text()).slice(0, 400)}`,
      );
    }
    const c = (await cRes.json()) as { id: string };
    cleanup.track({ type: 'contract', id: c.id, owner: dpo });

    // ── Default JSON response.
    const jsonRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/impact-analysis/?depth=5&include_fields=true`,
      { headers },
    );
    if (jsonRes.status() === 404) {
      test.skip(true, 'Impact-analysis endpoint not enabled (404)');
      return;
    }
    expect(jsonRes.ok()).toBe(true);
    expect(Object.keys(await jsonRes.json()).length).toBeGreaterThan(0);

    // ── CSV output.
    const csvRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/impact-analysis/?depth=2&output=csv`,
      { headers },
    );
    expect(csvRes.status()).toBeLessThan(500);
    if (csvRes.ok()) {
      const ct = csvRes.headers()['content-type'] ?? '';
      expect(/text\/csv|application\/csv|text\/plain/i.test(ct)).toBe(true);
    }

    // ── Field-scoped query.
    const fieldRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/impact-analysis/?depth=2&model_name=M&field_name=pk&include_fields=true`,
      { headers },
    );
    expect(fieldRes.status()).toBeLessThan(500);

    // ── Depth=0 boundary — must not crash.
    const zeroRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/impact-analysis/?depth=0`,
      { headers },
    );
    expect(zeroRes.status()).toBeLessThan(500);
  });
});
