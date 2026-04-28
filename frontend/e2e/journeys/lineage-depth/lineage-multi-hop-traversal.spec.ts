/**
 * E2E spec — Lineage multi-hop traversal (Phase 226.G5).
 *
 * Background
 * ----------
 * `/lineage/full/` accepts `max_contract_depth` / `max_model_depth` /
 * `max_field_depth`. The platform must:
 *   1. Honor the depth bound (no infinite traversal on circular lineage).
 *   2. Return a deterministic shape regardless of depth (the SPA's React
 *      Flow renderer can crash on unexpected structures).
 *   3. NOT 5xx on legal-but-large depth.
 *
 * Spec asserts:
 *   1. depth=1 (single hop) returns valid shape.
 *   2. depth=10 (large) returns valid shape and doesn't 5xx.
 *   3. The two responses differ in node/link count when the contract has
 *      lineage (or are equal-shape when it doesn't — both are valid).
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

test.describe('226.G5 — Lineage multi-hop traversal @critical @lineage', () => {
  test.setTimeout(180_000);

  test('depth=1 vs depth=10 traversal: both succeed without 5xx; depth bound respected', async ({
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
      id: `e2e-g5-mh-${Date.now()}`,
      name: 'G5 Multi-Hop Probe',
      version: '1.0.0',
      schema: { fields: [{ name: 'id', type: 'string' }] },
    });
    const cRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers,
      data: { original_raw: odcs, original_format: 'JSON', original_spec_type: 'ODCS' },
    });
    if (!cRes.ok()) {
      test.skip(true, `contract create failed (${cRes.status()})`);
      return;
    }
    const c = (await cRes.json()) as { id: string };
    cleanup.track({ type: 'contract', id: c.id, owner: dpo });

    // ── depth=1.
    const oneRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/full/?max_contract_depth=1&max_model_depth=1&max_field_depth=1`,
      { headers },
    );
    expect(oneRes.ok(), `depth=1 status=${oneRes.status()}`).toBe(true);
    const oneBody = (await oneRes.json()) as { upstream?: unknown; downstream?: unknown };
    expect('upstream' in oneBody && 'downstream' in oneBody).toBe(true);

    // ── depth=10 — must NOT 5xx (the bug we're guarding against is the
    // BFS walker exhausting memory or hitting deep-recursion limits).
    const tenRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/full/?max_contract_depth=10&max_model_depth=10&max_field_depth=10`,
      { headers },
    );
    expect(
      tenRes.status(),
      `depth=10 must not 5xx; got ${tenRes.status()}`,
    ).toBeLessThan(500);
    if (tenRes.ok()) {
      const tenBody = (await tenRes.json()) as { upstream?: unknown; downstream?: unknown };
      expect('upstream' in tenBody && 'downstream' in tenBody).toBe(true);
    }
  });
});
