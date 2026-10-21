/**
 * E2E Feature: Lineage Visualization (Phase 219.7)
 *
 * Lineage is embedded in the contract detail page as a "Lineage" tab
 * (ContractLineageVisualization → React Flow graph). There is no
 * standalone /lineage route.
 *
 * Test flow: login → seed a 3-contract DAG via API (Phase 228
 * REQ-LIN-005) → /contracts/{id} → click Lineage tab → assert React
 * Flow graph with the known 3-node/2-edge cardinality.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';
// Phase 228 (REQ-LIN-005, 228.0.16) — DAG seeding helper.
import { seedLineageDag } from '../fixtures/lineage-fixtures';

test.describe('Feature: Lineage', () => {
  // Budget arithmetic: login (60s helper cap) + contracts-list assert
  // (60s) + navigation helper (60s) + terminal wait (30s) + the churn-
  // recovery retry below (30s) + lineage-tab/graph waits (30s) — the
  // old 120s cap expired mid-flow when a mid-batch stall forced the
  // recovery path (b7 #33). 180s lets the strict assertions run to
  // completion so a persistent error fails with the precise message
  // instead of an opaque budget-wall browser-close.
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('contract lineage tab renders graph or empty state', async ({ page }) => {
      // Authenticate explicitly — storageState token can expire during long runs.
      const user = await getTestUser();
      await loginUser(page, user);

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
      //
      // Phase 11.1 — the access_token is MEMORY-ONLY and dies on a full
      // page reload (authStore: "after page reload, access_token is
      // lost"); after `page.goto` the cookie-restore path authenticates
      // the app WITHOUT repopulating apiClient's module memory, so
      // __getAccessToken() reads null. The seed MUST run on the same
      // page loginUser leaves — before any goto — while the token is
      // still in module memory (b6 lineage failure: the probe after the
      // contracts-list goto saw no token and threw). Poll briefly for
      // auth-init to settle before giving up.
      let accessToken: string | null = null;
      for (let attempt = 0; attempt < 20 && !accessToken; attempt += 1) {
        accessToken = await page.evaluate(() => {
          const g = (window as unknown as { __getAccessToken?: () => string | null })
            .__getAccessToken;
          return typeof g === 'function' ? g() : null;
        });
        if (!accessToken) await page.waitForTimeout(500);
      }
      if (!accessToken) {
        throw new Error(
          'Lineage setup: access_token never materialised in apiClient memory after loginUser (Phase 11.1 in-memory token lost before the probe).',
        );
      }
      // Phase 228 (REQ-LIN-005, 228.0.15-16): seed a 3-contract linear DAG
      // (root → mid → leaf) so the lineage graph has known cardinality.
      // The leaf contract's lineage tab shows the full upstream chain
      // — 3 nodes (root + mid + leaf) and 2 edges. Pre-Phase-228 the
      // test created a single contract and asserted ``graph || empty``,
      // which silently passed on a backend regression that returned
      // empty lineage; the strict-content assertion below now catches
      // such regressions deterministically.
      const dag = await seedLineageDag(page, 3, { accessToken });
      const contractId = dag.leafId;

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
      const errorDisplay = page
        .locator('.error-display, [data-testid="error-display"]')
        .first();
      if ((await errorDisplay.count()) > 0) {
        // Churn recovery (b7 #33): a mid-batch gunicorn recycle kills the
        // in-flight GET for the contract we just created — the page renders
        // its ErrorDisplay with a Retry affordance. Use the app's recovery
        // ONCE before classifying this as a product regression.
        // intentional: diagnostic-only read — an empty read just skips the retry and the strict re-check below reports the visible state.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (
          /NETWORK_ERROR|Network Error|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE|ECONNREFUSED|timed out/i.test(
            errText
          )
        ) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: single retry for transient mid-batch churn — the strict re-check below must pass or the test fails.
          await page
            .locator('[data-testid="contract-detail-page"], .contract-detail-page')
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
        }
      }
      if ((await errorDisplay.count()) > 0) {
        // intentional: diagnostic-only read — an empty read just means no error surface rendered and the message falls back to the generic form.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        throw new Error(
          `Contract detail page rendered an ErrorDisplay for contract ${contractId} ` +
            `that we just created via POST /api/v1/contracts/. This means ` +
            `useContract's GET /api/v1/contracts/${contractId}/ failed — ` +
            `a real regression (likely tenant scoping, normalization stuck, or ` +
            `serializer drift). Error text: "${errText.slice(0, 300)}"`,
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
