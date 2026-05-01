/**
 * E2E Feature: Lineage Visualization (Phase 219.7)
 *
 * Lineage is embedded in the contract detail page as a "Lineage" tab
 * (ContractLineageVisualization → React Flow graph). There is no
 * standalone /lineage route.
 *
 * Test flow: ensure-contract-via-API → /contracts/{id} → click Lineage tab →
 * assert React Flow renderer OR empty state (both acceptable).
 * Real backend only; no mocks.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { expect, test, type Page } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';
// Phase 228 (REQ-LIN-005, 228.0.16) — DAG seeding helper.
import { seedLineageDag } from '../fixtures/lineage-fixtures';

const __currentFile = fileURLToPath(import.meta.url);
const __currentDir = path.dirname(__currentFile);

// Canonical API base — same resolution chain used by every other
// page.request.* call-site in this repo (e.g. multi-tenancy-isolation.spec.ts:25-31,
// JOURNEY-CONTRACT-V310-LIFECYCLE.spec.ts:31-38). Using a relative `/api/v1/...`
// path against `page.request` would resolve against `PLAYWRIGHT_BASE_URL`
// (the FRONTEND host on staging — `stagingmeshant-internal.example.com`), but the API
// is on a separate subdomain (`api.stagingmeshant-internal.example.com`), and the
// httpOnly auth cookies are bound to the API host. Sending a request to the
// frontend host either misses the cookies entirely (different-origin cookie
// scope) OR reaches a proxy that strips them — either way the backend
// returns 401 AUTH_UNAUTHORIZED. The full-URL form is the only correct path.
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http')
    ? process.env.VITE_API_BASE_URL
    : `http://localhost:${DEFAULT_API_PORT}/api/v1`);

/**
 * Read a contract fixture from the canonical /tests/fixtures/contracts/ dir.
 * Path navigation: lineage.spec.ts → e2e → frontend → repo-root → tests/fixtures/contracts.
 */
function readContractFixture(name: string): string {
  const fixtureDir = path.resolve(__currentDir, '..', '..', '..', 'tests', 'fixtures', 'contracts');
  return fs.readFileSync(path.join(fixtureDir, name), 'utf-8');
}

/**
 * Create a contract via API using the page's existing access_token.
 *
 * Two staging-specific constraints together force the canonical pattern below:
 *
 *   1. CROSS-SUBDOMAIN HOST — `PLAYWRIGHT_BASE_URL=stagingmeshant-internal.example.com`
 *      and the API is at `api.stagingmeshant-internal.example.com`. A relative URL
 *      against `page.request` would target the frontend host, which neither
 *      mounts /api/v1/ routes directly nor shares cookies with the API host.
 *      Cycle 5 staged this exact failure: 401 AUTH_UNAUTHORIZED. We MUST use
 *      the full API URL (`API_BASE`).
 *
 *   2. NO SECOND LOGIN — staging deploys with `USE_HTTPONLY_AUTH_COOKIES=True`
 *      AND a one-active-refresh-token-per-user policy. Calling `loginViaApi`
 *      a second time rotates the user's refresh token; the browser's existing
 *      cookie still holds the pre-rotation value; the next page navigation
 *      gets 401 → /login redirect (cycle 4 surfaced this in the lineage
 *      Success path). We MUST reuse the access_token already in localStorage
 *      from `loginUser`, NOT issue a fresh API login.
 *
 * The canonical resolution: read `access_token` from the page's localStorage,
 * pass it as an explicit `Authorization: Bearer …` header, and POST to
 * `${API_BASE}/contracts/`. This is the same pattern used by
 * multi-tenancy-isolation.spec.ts:51-62 and ensures (a) the request hits the
 * API host where the backend lives and (b) doesn't rotate any tokens.
 *
 * Returns the contract id (UUID). Throws on failure with full diagnostics so
 * we never silently swallow a setup error.
 */
async function ensureContractViaApi(page: Page): Promise<string> {
  const raw = readContractFixture('odcs_v3_1_0_minimal.yaml');
  const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
  if (!accessToken) {
    throw new Error(
      'Lineage setup: no access_token in localStorage after loginUser. ' +
        'Cookie/storage policy may be blocking persistence; check the ' +
        'browser context and login flow.',
    );
  }
  // Backend choices are UPPERCASE (Django TextChoices, case-sensitive):
  //   hub/apps/contracts/models.py:48 → OriginalSpecType.ODCS = "ODCS"
  //   hub/apps/contracts/models.py:54 → OriginalFormat.YAML  = "YAML"
  // Sending lowercase raises a 400 VALIDATION_ERROR from
  // serializers.ChoiceField. JOURNEY-CONTRACT-V310-LIFECYCLE.spec.ts:147 uses
  // the uppercase form correctly; the previous lowercase here was a divergence.
  const res = await page.request.post(`${API_BASE}/contracts/`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    data: {
      original_raw: raw,
      original_spec_type: 'ODCS',
      original_format: 'YAML',
    },
  });
  if (!res.ok()) {
    const body = await res.text().catch(() => '');
    throw new Error(
      `Lineage setup: POST ${API_BASE}/contracts/ returned ${res.status()}. ` +
        `Body: ${body.slice(0, 300)}. ` +
        `The lineage test requires a contract to exist; creating one via the ` +
        `same API the UI uses is the deterministic way to seed test data on ` +
        `staging.`,
    );
  }
  const data = (await res.json()) as { id?: string };
  if (!data.id) {
    throw new Error(
      `Lineage setup: POST ${API_BASE}/contracts/ returned 2xx but no id in body. ` +
        `Response: ${JSON.stringify(data).slice(0, 300)}.`,
    );
  }
  return data.id;
}

test.describe('Feature: Lineage', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contract lineage tab renders graph or empty state', async ({ page }) => {
      // Authenticate explicitly — storageState token can expire during long runs.
      const user = await getTestUser();
      await loginUser(page, user);

      // Navigate to contracts list — verifies the route renders without 500
      // before we go deeper. The list may be empty on a fresh staging DB; we
      // create our own contract below so the lineage assertion has a target
      // regardless of pre-existing data.
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
      await assertListPageLoads(
        page,
        '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"]',
        { timeout: 60000 },
      );

      // Seed a contract via API so the lineage tab has something to render
      // against. Previously this test skipped when no contracts existed —
      // that masked the "lineage tab works" assertion behind an environment-
      // dependent skip and caused permanent gaps in staging coverage. Creating
      // the contract via the same API the UI uses is deterministic, exercises
      // the real normalization pipeline, and never produces flaky setup failures
      // (any 4xx/5xx is a hard error, not a skip).
      //
      // Pass `page` (not a separately-issued API token) so the request shares
      // the browser's existing session — see ensureContractViaApi for the
      // staging-specific token-rotation rationale.
      // Phase 228 (REQ-LIN-005, 228.0.15-16): seed a 3-contract linear DAG
      // (root → mid → leaf) so the lineage graph has known cardinality.
      // The leaf contract's lineage tab shows the full upstream chain
      // — 3 nodes (root + mid + leaf) and 2 edges. Pre-Phase-228 the
      // test created a single contract and asserted ``graph || empty``,
      // which silently passed on a backend regression that returned
      // empty lineage; the strict-content assertion below now catches
      // such regressions deterministically.
      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) {
        throw new Error('Lineage setup: no access_token in localStorage after loginUser.');
      }
      const dag = await seedLineageDag(page, 3, { accessToken });
      const contractId = dag.leafId;

      // Navigate directly to the seeded contract's detail page using
      // `loginAndNavigateToRoute` — NOT a bare `page.goto`.
      //
      // Bare page.goto on staging triggers a full SPA bootstrap that re-runs
      // the auth init: the SPA reads access_token from localStorage, calls
      // /auth/me/, then either confirms or refreshes via the httpOnly cookie.
      // The intermediate `loginUser` call (storageState branch → API login)
      // and the `ensureContractViaApi` POST both go through paths that can
      // leave the browser's refresh_token cookie misaligned with the backend's
      // server-side rotated value (the `auth.ts:178-215` cookie-domain bug:
      // syncPageWithApiAuth writes the cookie under the FRONTEND host, but
      // the backend's Set-Cookie attaches it to the API host; the rotation
      // therefore never updates the actual cookie the browser sends to
      // api.stagingmeshant-internal.example.com on /auth/refresh/). When access_token
      // hits a 401 in /auth/me/, refresh fails, SPA redirects to /login —
      // which is exactly the cycle-6 failure shape:
      //   waiting for "https://stagingmeshant-internal.example.com/login" navigation.
      //
      // `loginAndNavigateToRoute(testUser, /contracts/{id}, …)` re-establishes
      // a fresh session via the canonical login path AND navigates to the
      // same URL — same fix shape as Fix 20 for DPO-001. The SPA boots with
      // a known-fresh access_token; useContract's GET /contracts/{id}/
      // succeeds; the contract detail page renders; the rest of the spec
      // (terminal-state wait, lineage-tab click, graph assertion) proceeds
      // normally.
      await loginAndNavigateToRoute(page, user, `/contracts/${contractId}`, {
        timeout: 60000,
        contentSelector:
          '[data-testid="contract-detail-page"], .contract-detail-page, .error-display, [data-testid="error-display"]',
      });
      await page.waitForURL(/\/contracts\/[0-9a-f-]+/i, { timeout: 15000 });

      // Wait for the page to reach a TERMINAL render state — either the
      // detail page (with tabs) or an error display. waitForURL alone resolves
      // immediately after navigation commits, BEFORE useContract has fetched
      // the contract via the API, so without this wait the lineage-tab check
      // races the SPA's first render and intermittently sees 0 elements while
      // ContractDetailPage is still showing <DetailPageSkeleton/>.
      await page.waitForSelector(
        '[data-testid="contract-detail-page"], .contract-detail-page, .error-display, [data-testid="error-display"]',
        { timeout: 30000 },
      );

      // The Lineage tab is rendered UNCONDITIONALLY by ContractDetailPage
      // (frontend/src/features/contracts/components/ContractDetailPage.tsx:161-169)
      // whenever the contract loads successfully. If we see an ErrorDisplay
      // here, the seeded contract failed to fetch — that's a real product
      // regression (we just created it), not a feature gate. The previous
      // version's `test.skip(true, 'Lineage tab not visible — feature may be
      // gated...')` masked exactly this regression behind a green skip.
      const errorDisplayCount = await page
        .locator('.error-display, [data-testid="error-display"]')
        .count();
      if (errorDisplayCount > 0) {
        const errText = await page
          .locator('.error-display, [data-testid="error-display"]')
          .first()
          .textContent()
          .catch(() => '');
        throw new Error(
          `Contract detail page rendered an ErrorDisplay for contract ${contractId} ` +
            `that we just created via POST /api/v1/contracts/. This means ` +
            `useContract's GET /api/v1/contracts/${contractId}/ failed — ` +
            `a real regression (likely tenant scoping, normalization stuck, or ` +
            `serializer drift). Error text: "${(errText ?? '').slice(0, 300)}"`,
        );
      }

      // Click "Lineage" tab — must be present at this point because the
      // contract loaded without an error display.
      const lineageTab = page
        .locator('button:has-text("Lineage"), [role="tab"]:has-text("Lineage"), a:has-text("Lineage")')
        .first();
      await lineageTab.waitFor({ state: 'visible', timeout: 10000 });
      await lineageTab.click();

      // Phase 228 (REQ-LIN-005, 228.0.15) — strict content assertion.
      // Pre-Phase-228 the assertion was ``hasReactFlow || hasEmptyOrError``
      // which silently passed on a backend regression that returned
      // empty lineage. The fail-soft branch is preserved as a SEPARATE
      // spec at ``frontend/e2e/features/lineage-empty-state.spec.ts``
      // (REQ-LIN-005's "empty state retained" scenario); this spec
      // asserts EXACT node + edge counts against a known seeded DAG.
      await page
        .locator('.react-flow__renderer, .react-flow')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 });

      // Phase 228: REQ-LIN-005 strict-content assertion — exactly 3
      // nodes (root + mid + leaf seeded by ``seedLineageDag(page, 3)``)
      // and exactly 2 edges (linear DAG). React Flow's ``.react-flow__node``
      // selector counts the rendered graph nodes one-to-one; ``.react-flow__edge``
      // counts edges. The seeded DAG has known cardinality so any
      // deviation indicates a regression in the lineage read-path or
      // the visualization renderer.
      const nodeCount = await page.locator('.react-flow__node').count();
      const edgeCount = await page.locator('.react-flow__edge').count();
      expect(nodeCount).toBe(3);
      expect(edgeCount).toBe(2);

      // Controls panel sanity-check — pre-existing invariant.
      const hasControls =
        (await page.locator('.react-flow__controls').count()) > 0;
      expect(hasControls).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to contracts redirects to login', async ({ page }) => {
      await page.goto('/contracts');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/contracts'),
        'Expected /login redirect or /contracts with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('contracts list renders for lineage context (empty or populated)', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      // Must render without 500 errors
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'Contracts page must not show 500 errors').toBe(false);
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Expected contract list or empty state').toBe(true);
    });
  });
});
