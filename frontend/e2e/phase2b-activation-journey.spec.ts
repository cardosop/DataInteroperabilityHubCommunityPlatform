/**
 * Phase 2b — Asset Activation Golden Path
 *
 * Complements phase2-catalog-journey (creation) and phase3-quality-gates
 * (DQ/compliance). This spec exercises the *activation* chain end-to-end
 * so the E2E suite produces an ACTIVE asset on every successful run.
 *
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ Activation preconditions — from hub/apps/assets/models.py:276-323 │
 * ├──────────────────────────────────────────────────────────────────┤
 * │ MANDATORY                                                         │
 * │  * Asset has ≥1 contract with status=ACTIVE                       │
 * │  * That contract has validation_status ∈ {VALID, WARNING_ONLY}    │
 * │  * That contract has normalization_status ∈ {NORMALIZED_OK,       │
 * │    NORMALIZED_WITH_WARNINGS}                                      │
 * │ CONDITIONAL (only if the asset has a dataset attached)            │
 * │  * dq_status ∈ {PASS, WARN}                                       │
 * │  * compliance_status ∈ {PASS, WARN}                               │
 * └──────────────────────────────────────────────────────────────────┘
 *
 * We build the *contract-only* asset — the simplest activation path. No
 * dataset, so the conditional DQ/compliance checks are skipped entirely,
 * which also means the spec does not depend on the DQ/compliance workers
 * being healthy (those belong to phase3). The flow is therefore fully
 * deterministic and completes in a single run without polling async
 * jobs.
 *
 * The live reference for this shape is staging asset
 * 26f775ba-ee95-4434-99c5-cbce823b2a2d: ACTIVE, dataset_id=null,
 * dq_status/compliance_status=UNKNOWN, backed by a single ACTIVE
 * contract with NORMALIZED_OK + VALID-at-activation validation.
 *
 * Implementation choice — UI vs API per step
 * ------------------------------------------
 * * Asset create + asset activate run through the UI because those are
 *   the two user-facing activation surfaces and the UX contract there is
 *   what we actually want to guard. Both get a `verifyViaApi` backstop
 *   so "UI says succeeded + API says it didn't" is loud.
 * * Contract create, validate, and PATCH-status run through the API.
 *   Phase5 already drives the contract-create UI for the ODPS shape;
 *   duplicating it here would add minutes to the run without new UX
 *   coverage. The validate + activate UI paths on the contract side are
 *   thin wrappers that the DRF unit tests already cover; what's novel
 *   about this spec is the *composed chain*, which the API probe proves
 *   cleanly.
 *
 * This is the shape every future Tier-1 activation roll-out should follow.
 */

import { expect, test, type Page } from '@playwright/test';
import { getTestUser } from './fixtures/auth';
import {
  loginAndNavigateToRoute,
  navigateToRouteFromApp,
  waitForLoadingComplete,
} from './fixtures/helpers';
import { verifyViaApi } from './fixtures/verifyViaApi';

/**
 * Read the bearer token from page localStorage (where the app stores it
 * after login) so `page.request.*` — Playwright's Node-side HTTP client,
 * which is NOT subject to the page's CSP — can authenticate with the
 * same identity as the signed-in UI.
 *
 * Duplicated from phase5-odps-journey.spec.ts:27 and
 * fixtures/verifyViaApi.ts:49. Extract to a shared fixture in a
 * follow-up if a 4th caller appears.
 */
async function bearerHeaders(page: Page): Promise<Record<string, string>> {
  const token = await page.evaluate<string | null>(
    () =>
      (globalThis as unknown as { localStorage?: { getItem: (k: string) => string | null } })
        .localStorage?.getItem('access_token') ?? null,
  );
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Minimal valid ODCS v3 contract body. Shape and required fields cribbed
 * from the in-tenant reference contract b1dcf8a5 probed during the
 * Phase 2b precondition investigation (returned validation_status=VALID
 * from POST /contracts/<id>/validate/ on staging).
 */
function buildOdcsContractJson(): Record<string, unknown> {
  return {
    apiVersion: 'odcs/v3',
    kind: 'DataContract',
    id: `phase2b-odcs-${Date.now()}`,
    name: 'Phase 2b Activation ODCS',
    version: '1.0.0',
    schema: {
      fields: [
        { name: 'id', type: 'string', description: 'Unique identifier' },
        { name: 'name', type: 'string', description: 'Human-readable name' },
      ],
    },
  };
}

test.describe('Phase 2b — Asset Activation Golden Path', () => {
  test('create asset → create+validate+activate contract → activate asset (ACTIVE end-to-end)', async ({
    page,
  }) => {
    test.setTimeout(180_000);

    const testUser = await getTestUser();

    // ─────────────────────────────────────────────────────────────────
    // Step 1 — Create asset via UI (same pattern as phase2-catalog)
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 1: Creating asset via UI…');
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    // The Create button can live in three places — test them in priority order.
    const createButton = page
      .locator('.asset-list-header button:has-text("Create Asset")')
      .or(page.locator('[data-testid="empty-state-action"]:has-text("Create Asset")'))
      .or(page.locator('button:has-text("Create Asset")'));
    await createButton.first().waitFor({ timeout: 15000 });
    await createButton.first().click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });

    // React Hook Form — target accessible labels, not implementation-detail ids.
    const assetKey = `phase2b-asset-${Date.now()}`;
    await page.getByLabel('Key').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByLabel('Key').fill(assetKey);
    await page.getByLabel('Name').fill('Phase 2b Activation Asset');
    await page.getByLabel('Description').fill('Golden-path activation test asset');
    await page.getByLabel('Visibility').selectOption('INTERNAL');

    const submitButton = page.locator('button:has-text("Create Asset")');
    await submitButton.waitFor({ timeout: 10000 });
    await submitButton.click();

    const uuidRegex = /\/assets\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i;
    try {
      await page.waitForURL(uuidRegex, { timeout: 60000, waitUntil: 'domcontentloaded' });
    } catch {
      // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
      const errEl = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
      const errHint = errEl ? ` Backend error: ${errEl.slice(0, 200)}` : '';
      throw new Error(`Asset create redirect timed out. Current URL: ${page.url()}.${errHint}`);
    }
    const assetId = page.url().match(uuidRegex)?.[1];
    if (!assetId) {
      throw new Error(`Invalid asset ID from URL: ${page.url()}`);
    }

    // Dual-channel: UI routed, now confirm the row exists server-side.
    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
      key: assetKey,
      status: 'DRAFT',
    });
    console.log(`Asset created: ${assetId} (DRAFT)`);

    // ─────────────────────────────────────────────────────────────────
    // Step 2 — Create contract linked to asset (API)
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 2: Creating ODCS contract linked to asset via API…');
    const createContractHeaders = {
      'Content-Type': 'application/json',
      ...(await bearerHeaders(page)),
    };
    const createContractRes = await page.request.post('/api/v1/contracts/', {
      headers: createContractHeaders,
      data: {
        asset_id: assetId,
        original_spec_type: 'ODCS',
        original_spec_version: '3.0.0',
        original_format: 'JSON',
        original_raw: JSON.stringify(buildOdcsContractJson()),
      },
    });
    if (!createContractRes.ok()) {
      // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
      const body = await createContractRes.text().catch(() => '');
      throw new Error(
        `Contract create failed: ${createContractRes.status()} — ${body.slice(0, 400)}`,
      );
    }
    const contract = (await createContractRes.json()) as { id: string; version: number };
    const contractId = contract.id;
    console.log(`Contract created: ${contractId} (DRAFT)`);

    // ─────────────────────────────────────────────────────────────────
    // Step 3 — Validate contract synchronously (API)
    //
    // hub/apps/contracts/views_validation.py:180 — POST /contracts/<id>/validate/
    // with {"async": false} runs the DataContract CLI inline and updates
    // validation_status + normalization_status. This is the only way to
    // lift validation_status off of null; activation requires VALID or
    // WARNING_ONLY (see models.py:291).
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 3: Validating contract synchronously via API…');
    const validateRes = await page.request.post(
      `/api/v1/contracts/${contractId}/validate/`,
      {
        headers: createContractHeaders,
        data: { async: false },
      },
    );
    if (!validateRes.ok()) {
      // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
      const body = await validateRes.text().catch(() => '');
      throw new Error(
        `Contract validate failed: ${validateRes.status()} — ${body.slice(0, 400)}`,
      );
    }
    const validateBody = (await validateRes.json()) as {
      validation_status: string;
      normalization_status: string;
    };
    console.log(
      `Validation result: validation=${validateBody.validation_status} normalization=${validateBody.normalization_status}`,
    );
    // Fail loud if the precondition wasn't met — tells us the synthetic
    // ODCS content drifted from what the CLI accepts.
    expect(
      ['VALID', 'WARNING_ONLY'],
      `Contract ${contractId} validation_status was ${validateBody.validation_status}; ` +
        `activation requires VALID or WARNING_ONLY. The synthetic contract body may have ` +
        `drifted — update buildOdcsContractJson() to match the current ODCS schema.`,
    ).toContain(validateBody.validation_status);
    expect(
      ['NORMALIZED_OK', 'NORMALIZED_WITH_WARNINGS'],
      `Contract ${contractId} normalization_status was ${validateBody.normalization_status}; ` +
        `activation requires NORMALIZED_OK or NORMALIZED_WITH_WARNINGS.`,
    ).toContain(validateBody.normalization_status);

    // ─────────────────────────────────────────────────────────────────
    // Step 4 — Activate contract (API, PATCH status)
    //
    // Contract lifecycle transitions go through PATCH /contracts/<id>/
    // with {status, version}. See hub/apps/contracts/business_rules.py:1748
    // for the valid-transition matrix (DRAFT → ACTIVE is permitted).
    // Optimistic locking: `version` must match the current server version.
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 4: Activating contract via API (PATCH status=ACTIVE)…');
    // Re-read current version — the validate step may have bumped it.
    const contractPreActivate = await verifyViaApi<{ version: number; status: string }>(
      page,
      `/api/v1/contracts/${contractId}/`,
      (body: { status: string }) => body.status === 'DRAFT',
    );
    const activateContractRes = await page.request.patch(
      `/api/v1/contracts/${contractId}/`,
      {
        headers: createContractHeaders,
        data: { status: 'ACTIVE', version: contractPreActivate.version },
      },
    );
    if (!activateContractRes.ok()) {
      // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
      const body = await activateContractRes.text().catch(() => '');
      throw new Error(
        `Contract activate failed: ${activateContractRes.status()} — ${body.slice(0, 400)}`,
      );
    }
    // Dual-channel: GET the contract and prove it's ACTIVE with the
    // validation invariants intact (they'll be asserted by asset-activate
    // next, but failing here gives a clearer diagnostic).
    await verifyViaApi(
      page,
      `/api/v1/contracts/${contractId}/`,
      (body: { status: string; validation_status: string; normalization_status: string }) =>
        body.status === 'ACTIVE' &&
        ['VALID', 'WARNING_ONLY'].includes(body.validation_status) &&
        ['NORMALIZED_OK', 'NORMALIZED_WITH_WARNINGS'].includes(body.normalization_status),
    );
    console.log(`Contract ${contractId} → ACTIVE`);

    // ─────────────────────────────────────────────────────────────────
    // Step 5 — Activate asset via UI (the primary UX being guarded)
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 5: Activating asset via UI…');
    await navigateToRouteFromApp(page, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, [data-testid="asset-detail-page"], .asset-detail-content, h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const activateAssetButton = page.locator('button:has-text("Activate Asset")');
    await activateAssetButton.waitFor({ state: 'visible', timeout: 15000 });
    // Must be enabled — preconditions are met, so the disabled-due-to-blockers
    // code path in the UI should have lifted. If the button stays disabled
    // here, that's a real UI regression worth seeing red.
    await expect(activateAssetButton).toBeEnabled();

    // Observe the activate POST directly so we diagnose 4xx/5xx without
    // waiting for a UI-level badge update.
    const activateResponsePromise = page.waitForResponse(
      (r) => r.url().includes(`/assets/${assetId}/activate/`) && r.request().method() === 'POST',
      { timeout: 30000 },
    );
    await activateAssetButton.click();
    const activateResponse = await activateResponsePromise;
    const activateStatus = activateResponse.status();
    if (activateStatus !== 200) {
      // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
      const body = await activateResponse.text().catch(() => '');
      throw new Error(
        `POST /assets/${assetId}/activate/ returned ${activateStatus}. Body: ${body.slice(0, 400)}. ` +
          `If this is an ASSET_ACTIVATION_BLOCKED, re-inspect the contract's validation_status ` +
          `and normalization_status — they may have drifted between Step 3 and Step 5.`,
      );
    }

    // ─────────────────────────────────────────────────────────────────
    // Step 6 — Dual-channel confirmation: API says ACTIVE, UI shows ACTIVE
    // ─────────────────────────────────────────────────────────────────
    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
      status: 'ACTIVE',
    });
    console.log(`Asset ${assetId} → ACTIVE (API-verified)`);

    // The UI updates via React Query invalidation on mutation success;
    // poll the badge briefly to cover the invalidation-then-refetch
    // round-trip (one network round-trip plus one render cycle).
    await expect(page.locator('.status-badge').first()).toContainText('ACTIVE', {
      timeout: 15000,
    });
    console.log(`Asset ${assetId} → ACTIVE (UI-verified)`);
  });
});
