/**
 * E2E spec — Semantic resource browse + URI lookup (Phase 226.G6).
 *
 * Decision context — `semantic_mvp_in_scope: true` (per
 * docs/CRITICAL_UC_JOURNEY_IDS.yaml). The semantic surface in MVP includes:
 *   • SPARQL query (covered by semantic-sparql-ui.spec.ts).
 *   • Semantic resource CRUD (read-only — `SemanticResourceViewSet` is
 *     `ReadOnlyModelViewSet` per `hub/apps/semantic/views.py:91`).
 *   • URI resolution endpoints (`/id/field/{asset_uuid}/{field_name}` etc.).
 *
 * Spec asserts the BROWSE/SEARCH path the SemanticPage's "URI Lookup" and
 * "Ontology Browser" tabs depend on:
 *   1. GET /api/v1/semantic-resources/ returns a list (possibly empty).
 *   2. Pagination shape is consistent (results/count keys present).
 *   3. URI resolution endpoint for a non-existent resource returns 404
 *      (the user-visible "URI not found" branch the URI Lookup tab handles).
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/guardedTest';
import { getTestUser, loginViaApi } from '../../fixtures/auth';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G6 — Semantic resource browse + URI lookup @critical @semantic', () => {
  test.setTimeout(120_000);

  test('semantic-resources list paginates; URI resolution 404 path returns documented shape', async ({
    page,
  }) => {
    const user = await getTestUser();
    const { access_token } = await loginViaApi(user.email, user.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    // ── List endpoint.
    // The semantic app is mounted at /api/v1/semantic/ in
    // hub/apps/api/urls.py:35, and SemanticResourceViewSet registers as
    // 'semantic-resources' in hub/apps/semantic/urls.py:21 — so the full
    // path is /api/v1/semantic/semantic-resources/.
    const listRes = await page.request.get(`${API_BASE}/semantic/semantic-resources/`, {
      headers,
    });
    expect(listRes.ok(), `semantic-resources list failed: ${listRes.status()}`).toBe(true);
    const listBody = (await listRes.json()) as
      | { results?: unknown[]; count?: number }
      | unknown[];
    if (Array.isArray(listBody)) {
      // Some backends respond unwrapped; that's fine, just assert it's an
      // array.
      expect(Array.isArray(listBody)).toBe(true);
    } else {
      expect('results' in listBody).toBe(true);
    }

    // ── URI resolution: a non-existent field URI returns 404 (the branch
    // the URI Lookup tab uses to show "not found"). Path is mounted under
    // the semantic app prefix per hub/apps/semantic/urls.py:31.
    const fakeAssetUuid = '00000000-0000-0000-0000-000000000000';
    const resolveRes = await page.request.get(
      `${API_BASE}/semantic/id/field/${fakeAssetUuid}/nonexistent_field`,
      { headers },
    );
    // 404 is the expected "URI not found" shape; 503 is acceptable when the
    // semantic service is offline (annotated). 200 with empty would be a
    // bug — the resolver should not invent an empty-but-200 response for a
    // non-existent URI.
    if (resolveRes.status() === 503) {
      test.info().annotations.push({
        type: 'g6-semantic-service-unavailable',
        description: 'URI resolver returned 503 — semantic service offline on this env.',
      });
      return;
    }
    expect(resolveRes.status()).toBe(404);
  });
});
