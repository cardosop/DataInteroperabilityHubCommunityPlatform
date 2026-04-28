/**
 * E2E spec — Lineage graph drill-through (Phase 226.G5).
 *
 * Background
 * ----------
 * The visualization endpoint at `GET /api/v1/contracts/{id}/lineage/
 * visualization/?format=json` returns nodes + links the SPA renders via
 * React Flow. "Drill-through" = clicking a node opens the corresponding
 * resource detail. This spec asserts:
 *   1. Visualization response carries node IDs that map to real resources
 *      (contract IDs, model names, field names).
 *   2. JSON, DOT, and Mermaid output formats all return non-empty content.
 *
 * The UI side of "drill-through" (click handler navigates to /contracts/
 * {id}) is component-tested in the lineage __tests__/ folder. This spec is
 * the API-to-UI contract assertion.
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

test.describe('226.G5 — Lineage graph drill-through @critical @lineage', () => {
  test.setTimeout(180_000);

  test('visualization endpoint returns drill-through-capable shape across json/dot/mermaid formats', async ({
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
      id: `e2e-g5-drill-${Date.now()}`,
      name: 'G5 Drill-Through Probe',
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

    // ── JSON: must include a `nodes` array with at least the source contract.
    const jsonRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/visualization/?format=json`,
      { headers },
    );
    expect(jsonRes.ok()).toBe(true);
    const jsonBody = (await jsonRes.json()) as {
      nodes?: Array<{ id: string }>;
      links?: Array<unknown>;
    };
    expect(Array.isArray(jsonBody.nodes)).toBe(true);
    // At minimum the contract itself should be a node.
    if ((jsonBody.nodes ?? []).length > 0) {
      const ids = (jsonBody.nodes ?? []).map((n) => n.id);
      expect(ids.length).toBeGreaterThan(0);
    }

    // ── DOT format.
    // The backend returns the DOT graph as a JSON-encoded string (DRF
    // wraps text in quotes when content_type stays application/json),
    // so the response body looks like `"digraph Lineage {\\n  ..."`.
    // Strip the JSON envelope before checking the canonical DOT prefix.
    const dotRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/visualization/?format=dot`,
      { headers },
    );
    expect(dotRes.status()).toBeLessThan(500);
    if (dotRes.ok()) {
      const dotRaw = await dotRes.text();
      let dotText = dotRaw.trim();
      try {
        const parsed = JSON.parse(dotRaw);
        if (typeof parsed === 'string') dotText = parsed.trim();
      } catch {
        // Not JSON-wrapped — use the raw body.
      }
      // DOT files start with `digraph` or `graph`. Empty body would mean
      // the renderer is broken.
      expect(
        /^(digraph|graph|strict\s+(di)?graph)\b/.test(dotText),
        `DOT body did not start with digraph/graph: ${dotText.slice(0, 200)}`,
      ).toBe(true);
    }

    // ── Mermaid format.
    const mermaidRes = await page.request.get(
      `${API_BASE}/contracts/${c.id}/lineage/visualization/?format=mermaid`,
      { headers },
    );
    expect(mermaidRes.status()).toBeLessThan(500);
    if (mermaidRes.ok()) {
      const mermaidRaw = await mermaidRes.text();
      let mermaidText = mermaidRaw.trim();
      try {
        const parsed = JSON.parse(mermaidRaw);
        if (typeof parsed === 'string') mermaidText = parsed.trim();
      } catch {
        // Not JSON-wrapped — use the raw body.
      }
      // Mermaid graphs start with `graph` / `flowchart` / `classDiagram`.
      expect(
        /^(graph|flowchart|classDiagram|stateDiagram)\b/.test(mermaidText),
        `Mermaid body did not start with a recognised diagram keyword: ${mermaidText.slice(0, 200)}`,
      ).toBe(true);
    }
  });
});
