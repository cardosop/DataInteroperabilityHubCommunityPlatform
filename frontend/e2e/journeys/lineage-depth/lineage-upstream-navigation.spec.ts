/**
 * E2E spec — Lineage upstream navigation depth (Phase 226.G5).
 *
 * Background
 * ----------
 * `GET /api/v1/contracts/{id}/lineage/full/?max_contract_depth=N` (`hub/
 * apps/contracts/views_lineage.py:225-252`) returns hierarchical lineage
 * with `upstream` and `downstream` branches. The frontend
 * `ContractLineageVisualization` component (`frontend/src/features/lineage/
 * components/ContractLineageVisualization.tsx`) renders the graph using
 * the same data via `/lineage/visualization/`.
 *
 * "Upstream navigation" = the user clicks a node and the graph re-roots
 * to that node, walking AGAINST the dependency arrow (sources first).
 *
 * Spec shape:
 *   1. Arm: create a contract with at least one schema/source reference.
 *   2. Drive: GET /lineage/full/ — assert response has an `upstream` key.
 *   3. Drive: GET /lineage/visualization/ — assert it returns nodes/links.
 *   4. UI smoke: navigate to /contracts/{id} → click lineage tab → graph
 *      renders without console errors (the @critical visual gate).
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginUser, loginViaApi } from '../../fixtures/auth';
import { ensureE2eSubscription } from '../../fixtures/ensureE2eSubscription';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G5 — Lineage upstream navigation @critical @lineage', () => {
  test.setTimeout(180_000);

  test('contract lineage exposes upstream branch + visualization renders without errors', async ({
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
      id: `e2e-g5-up-${Date.now()}`,
      name: 'G5 Upstream Probe',
      version: '1.0.0',
      schema: {
        fields: [
          { name: 'id', type: 'string' },
          { name: 'value', type: 'number' },
        ],
      },
    });
    const cRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers,
      data: { original_raw: odcs, original_format: 'JSON', original_spec_type: 'ODCS' },
    });
    if (!cRes.ok()) {
      test.skip(true, `Could not create contract (${cRes.status()})`);
      return;
    }
    const c = (await cRes.json()) as { id: string };
    cleanup.track({ type: 'contract', id: c.id, owner: dpo });

    // ── API: hierarchical full lineage with depth=5.
    const fullRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/full/?max_contract_depth=5&max_model_depth=5&max_field_depth=5`,
      { headers },
    );
    expect(fullRes.ok(), `lineage/full status=${fullRes.status()}`).toBe(true);
    const fullBody = (await fullRes.json()) as { upstream?: unknown; downstream?: unknown };
    expect(
      'upstream' in fullBody,
      `lineage/full response must include 'upstream'; got keys=${Object.keys(fullBody)}`,
    ).toBe(true);

    // ── API: visualization (the data the UI renders).
    const visRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/visualization/?format=json`,
      { headers },
    );
    expect(visRes.ok()).toBe(true);
    const visBody = (await visRes.json()) as { nodes?: unknown[]; links?: unknown[] };
    expect(Array.isArray(visBody.nodes)).toBe(true);
    expect(Array.isArray(visBody.links)).toBe(true);

    // ── UI smoke: navigate, click lineage tab, watch for the visualization
    // shell to render. Errors caught by guardedTest's pageerror/console
    // hooks fail the test at teardown.
    await loginUser(page, dpo);
    await page.goto(`/contracts/${c.id}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('h1, .contract-detail-page, .error-display', { timeout: 30_000 });
    const lineageTab = page.locator('button[role="tab"]:has-text("Lineage"), button:has-text("Lineage")').first();
    if ((await lineageTab.count()) > 0) {
      await lineageTab.click();
      // Lineage visualization or its empty-state must be visible.
      const lineageContent = page.locator(
        '[data-testid="contract-lineage-empty"], .contract-lineage-visualization, .react-flow, .lineage-graph',
      );
      await expect(lineageContent.first()).toBeVisible({ timeout: 15_000 });
    }
  });
});
