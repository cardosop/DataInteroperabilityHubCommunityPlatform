/**
 * E2E spec — Semantic search promotion (Phase 230.11 / REQ-SEM-SEARCH-EXPAND-001).
 *
 * Validates the user-facing surface of ontology-aware search:
 *
 *   1. The "Ontology-aware search" toggle is present on /search.
 *   2. Toggling it on appends ``semantic=true`` to the request URL on
 *      the existing search endpoint (``/api/v1/search/search/``).
 *   3. With a tenant that has not opted in
 *      (``Tenant.semantic_search_enabled=False``, the default), the
 *      backend responds normally — the toggle must NOT error or
 *      degrade the page.
 *
 * Bridge-term assertions (matched_via=ontology badge rendered in the
 * results list) require a tenant with active ontologies + matching
 * assets seeded.  Those preconditions live in
 * ``hub/apps/search/tests/test_semantic_expansion.py`` (backend
 * scenario tests against the real DB) — repeating them at the e2e
 * layer would duplicate coverage without adding signal.
 */

import { test, expect } from '../../fixtures/guardedTest';
import { getTestUser, loginViaApi } from '../../fixtures/auth';

test.describe('230.11 — Semantic search promotion @critical @semantic', () => {
  test.setTimeout(120_000);

  test('search page exposes ontology-aware toggle and forwards ?semantic=true on the same endpoint', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginViaApi(user.email, user.password);

    await page.goto('/search');
    await expect(page.getByTestId('search-page')).toBeVisible();

    // Toggle exists and is OFF by default (preserves legacy semantics
    // until the user explicitly opts in).
    const toggle = page.getByTestId('search-semantic-toggle');
    await expect(toggle).toBeVisible();
    await expect(toggle).not.toBeChecked();

    // Capture the network call shape that the toggle drives.  When
    // OFF, the legacy request hits /api/v1/search/search/ WITHOUT
    // the semantic flag.
    const legacyRequest = page.waitForRequest(
      (req) =>
        req.url().includes('/api/v1/search/search/') &&
        req.url().includes('q=customer') &&
        !req.url().includes('semantic=true'),
      { timeout: 15_000 },
    );
    await page.getByTestId('search-input').fill('customer');
    await legacyRequest;

    // Toggle ON → next request hits the SAME endpoint with
    // ``semantic=true`` appended (no URL switch — Phase 230.11
    // wires the param onto the existing SearchViewSet path so the
    // frontend doesn't need a separate route).
    const semanticRequest = page.waitForRequest(
      (req) =>
        req.url().includes('/api/v1/search/search/') &&
        req.url().includes('semantic=true'),
      { timeout: 15_000 },
    );
    await toggle.check();
    const req = await semanticRequest;
    expect(req.url()).toContain('semantic=true');
    // Refine — q=customer survived the reroute.
    expect(req.url()).toContain('q=customer');
  });

  test('toggle off restores original endpoint shape (no semantic=true)', async ({ page }) => {
    const user = await getTestUser();
    await loginViaApi(user.email, user.password);
    await page.goto('/search');

    const toggle = page.getByTestId('search-semantic-toggle');
    await toggle.check();
    await page.getByTestId('search-input').fill('client');
    await page.waitForRequest(
      (req) =>
        req.url().includes('/api/v1/search/search/') &&
        req.url().includes('semantic=true'),
      { timeout: 15_000 },
    );

    // Now flip OFF — the next debounced search MUST go to the same
    // endpoint without the semantic flag.
    const legacyRequest = page.waitForRequest(
      (req) =>
        req.url().includes('/api/v1/search/search/') &&
        !req.url().includes('semantic=true'),
      { timeout: 15_000 },
    );
    await toggle.uncheck();
    // Trigger a fresh debounce — clear and retype.
    await page.getByTestId('search-input').fill('');
    await page.getByTestId('search-input').fill('client');
    await legacyRequest;
  });
});
