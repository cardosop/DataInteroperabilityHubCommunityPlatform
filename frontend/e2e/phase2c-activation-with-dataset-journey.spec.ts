/**
 * Phase 2c — Asset Activation Golden Path WITH Dataset
 *
 * Companion to phase2b (contract-only activation). This spec exercises
 * the full dataset-attached activation chain, which is the shape most
 * real users take and which adds three extra preconditions enforced by
 * hub/apps/assets/models.py:307-321:
 *
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ When an asset has a dataset, activation additionally requires:   │
 * │  * dq_status ∈ {PASS, WARN}                                       │
 * │  * compliance_status ∈ {PASS, WARN}                               │
 * └──────────────────────────────────────────────────────────────────┘
 *
 * Those asset-level fields are not set directly — they're written as a
 * side effect when a DQ / Compliance run reaches a terminal status
 * (see hub/apps/dq/views.py:846-859 and
 * hub/apps/compliance/services.py:406-408). So the flow is:
 *
 *   create asset (UI)
 *   → create file + dataset linked to asset (API — reuses createDatasetViaApi)
 *   → create + validate + activate contract (API — same shape as phase2b)
 *   → start DQ run → poll to terminal → backend writes asset.dq_status
 *   → start Compliance run → poll to terminal → backend writes asset.compliance_status
 *   → activate asset (UI) — every precondition now met
 *   → dual-channel verify ACTIVE
 *
 * Unlike phase2b, this path depends on Celery workers (DQ, Compliance).
 * When those are down on staging we don't have a way to manufacture a
 * terminal run state — we skip the test with a specific reason so the
 * per-reason skip-counter gate (PR 10) fires at the configured
 * threshold rather than silently going green.
 *
 * One ACTIVE asset WITH a linked dataset per successful staging run.
 */

import { expect, test, type Page } from '@playwright/test';
import { getTestUser } from './fixtures/auth';
import { createDatasetViaApi } from './fixtures/api-assets';
import {
  loginAndNavigateToRoute,
  navigateToRouteFromApp,
  waitForLoadingComplete,
} from './fixtures/helpers';
import { verifyViaApi } from './fixtures/verifyViaApi';

/**
 * Bearer extraction from page localStorage so `page.request.*` (Node-side,
 * not subject to page CSP) authenticates as the signed-in UI user.
 * Mirror of phase2b and phase5; extract to a shared fixture in a
 * follow-up once a 4th caller appears.
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
 * Minimal valid ODCS v3 contract body — same shape proven to validate
 * VALID on staging in the phase2b precondition probe.
 */
function buildOdcsContractJson(): Record<string, unknown> {
  return {
    apiVersion: 'odcs/v3',
    kind: 'DataContract',
    id: `phase2c-odcs-${Date.now()}`,
    name: 'Phase 2c Activation ODCS',
    version: '1.0.0',
    schema: {
      fields: [
        { name: 'id', type: 'string', description: 'Unique identifier' },
        { name: 'name', type: 'string', description: 'Human-readable name' },
      ],
    },
  };
}

/**
 * Poll `/api/v1/{runsPath}/<id>/` until `status` reaches a terminal
 * value (SUCCEEDED / FAILED / CANCELLED). Returns the terminal status
 * string, or null if the timeout fired — callers decide whether to
 * skip, warn, or throw.
 *
 * Separate from phase5's pollWorkflowStatus because the shape differs
 * (workflow has PENDING/RUNNING/COMPLETED/FAILED; DQ/Compliance runs
 * have QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED) and collapsing them
 * into one generic helper would require an awkward config arg for tiny
 * readability gain.
 */
async function pollRunTerminalStatus(
  page: Page,
  runsPath: 'dq/runs' | 'compliance/runs',
  runId: string,
  opts: { timeoutMs: number; pollEveryMs: number },
): Promise<string | null> {
  const deadline = Date.now() + opts.timeoutMs;
  while (Date.now() < deadline) {
    const headers = await bearerHeaders(page);
    const res = await page.request.get(`/api/v1/${runsPath}/${runId}/`, { headers });
    if (res.ok()) {
      const body = (await res.json()) as { status?: string };
      if (body.status && ['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(body.status)) {
        return body.status;
      }
    }
    // Intentionally keep retrying on transient non-200s (auth refresh
    // race, 502 from proxy during deploy) — the poll budget will still
    // bound total wait. Non-transient failures surface via the final
    // null return.
    await page.waitForTimeout(opts.pollEveryMs);
  }
  return null;
}

test.describe('Phase 2c — Asset Activation WITH Dataset (full golden path)', () => {
  test('create asset + dataset → create+validate+activate contract → DQ+Compliance PASS → activate asset', async ({
    page,
  }) => {
    // 6 minutes. Worst-case budget: asset create (15s) + dataset create
    // with S3 PUT (30s) + contract create/validate/activate (20s) + DQ
    // terminal (up to 120s) + Compliance terminal (up to 180s) + asset
    // activate (15s). 360s gives headroom for staging jitter.
    test.setTimeout(360_000);

    const testUser = await getTestUser();

    // ─────────────────────────────────────────────────────────────────
    // Step 1 — Create asset via UI
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 1: Creating asset via UI…');
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const createButton = page
      .locator('.asset-list-header button:has-text("Create Asset")')
      .or(page.locator('[data-testid="empty-state-action"]:has-text("Create Asset")'))
      .or(page.locator('button:has-text("Create Asset")'));
    await createButton.first().waitFor({ timeout: 15000 });
    await createButton.first().click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });

    const assetKey = `phase2c-asset-${Date.now()}`;
    await page.getByLabel('Key').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByLabel('Key').fill(assetKey);
    await page.getByLabel('Name').fill('Phase 2c Activation Asset');
    await page.getByLabel('Description').fill('Full-chain activation test asset (with dataset)');
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
    if (!assetId) throw new Error(`Invalid asset ID from URL: ${page.url()}`);

    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
      key: assetKey,
      status: 'DRAFT',
    });
    console.log(`Asset created: ${assetId} (DRAFT)`);

    // ─────────────────────────────────────────────────────────────────
    // Step 2 — Create file + dataset linked to asset (API)
    //
    // Reuses createDatasetViaApi (fixtures/api-assets.ts:620) which runs
    // POST /files/init/ → PUT presigned URL → POST /files/<id>/complete/
    // → POST /datasets/. forceNew guarantees a fresh dataset (otherwise
    // the helper reuses any dataset already linked to a prior asset).
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 2: Creating file + dataset linked to asset via API…');
    const datasetId = await createDatasetViaApi(testUser, { assetId, forceNew: true });
    console.log(`Dataset created: ${datasetId} (linked to asset ${assetId})`);

    // Confirm the asset now reports dataset_id — the attach is what
    // causes can_activate() to enforce the DQ/Compliance preconditions.
    await verifyViaApi(
      page,
      `/api/v1/assets/${assetId}/`,
      (body: { dataset_id?: string | null }) => body.dataset_id === datasetId,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 3 — Create + validate + activate contract (API)
    //
    // Same three-call shape as phase2b. Duplicated (not factored into
    // a shared helper) because these specs are the template for
    // future Tier-1 activation journeys; keeping the chain visible
    // in-file helps the next reader understand what's required.
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 3a: Creating ODCS contract linked to asset…');
    const writeHeaders = {
      'Content-Type': 'application/json',
      ...(await bearerHeaders(page)),
    };
    const createContractRes = await page.request.post('/api/v1/contracts/', {
      headers: writeHeaders,
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
    const contract = (await createContractRes.json()) as { id: string };
    const contractId = contract.id;

    console.log('Step 3b: Validating contract synchronously…');
    const validateRes = await page.request.post(
      `/api/v1/contracts/${contractId}/validate/`,
      { headers: writeHeaders, data: { async: false } },
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
    expect(
      ['VALID', 'WARNING_ONLY'],
      `Contract ${contractId} validation_status was ${validateBody.validation_status}; ` +
        `activation requires VALID or WARNING_ONLY. Update buildOdcsContractJson() ` +
        `if the ODCS schema has moved.`,
    ).toContain(validateBody.validation_status);
    expect(
      ['NORMALIZED_OK', 'NORMALIZED_WITH_WARNINGS'],
      `Contract ${contractId} normalization_status was ${validateBody.normalization_status}.`,
    ).toContain(validateBody.normalization_status);

    console.log('Step 3c: Activating contract (PATCH status=ACTIVE)…');
    const contractPreActivate = await verifyViaApi<{ version: number; status: string }>(
      page,
      `/api/v1/contracts/${contractId}/`,
      (body: { status: string }) => body.status === 'DRAFT',
    );
    const activateContractRes = await page.request.patch(
      `/api/v1/contracts/${contractId}/`,
      {
        headers: writeHeaders,
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
    await verifyViaApi(
      page,
      `/api/v1/contracts/${contractId}/`,
      (body: { status: string }) => body.status === 'ACTIVE',
    );
    console.log(`Contract ${contractId} → ACTIVE`);

    // ─────────────────────────────────────────────────────────────────
    // Step 4 — Run DQ Check (API) and poll to terminal status.
    //
    // When the run reaches SUCCEEDED the backend writes asset.dq_status
    // (hub/apps/dq/views.py:846-859). If it reaches FAIL, activation
    // will be correctly blocked in Step 6 — we fail the test loud there
    // rather than silently skipping, because a FAIL against a 2-row
    // synthetic CSV indicates real DQ-profile drift worth investigating.
    //
    // If it doesn't reach any terminal state within the budget, the
    // DQ Celery worker is almost certainly down — skip with a specific
    // reason so the PR 10 skip-counter gate fires if this recurs.
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 4: Starting DQ run via API…');
    const dqStartRes = await page.request.post('/api/v1/dq/runs/', {
      headers: writeHeaders,
      data: { asset_id: assetId, dataset_id: datasetId },
    });
    if (!dqStartRes.ok()) {
      // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
      const body = await dqStartRes.text().catch(() => '');
      throw new Error(`DQ run start failed: ${dqStartRes.status()} — ${body.slice(0, 400)}`);
    }
    const dqRun = (await dqStartRes.json()) as { id: string };
    console.log(`DQ run started: ${dqRun.id}`);

    const dqTerminal = await pollRunTerminalStatus(page, 'dq/runs', dqRun.id, {
      timeoutMs: 120_000,
      pollEveryMs: 3_000,
    });
    test.skip(
      dqTerminal === null,
      'DQ worker did not finish the run within 120s — skip (PR 10 per-reason gate).',
    );
    if (dqTerminal === null) return;
    console.log(`DQ run ${dqRun.id} → ${dqTerminal}`);

    // ─────────────────────────────────────────────────────────────────
    // Step 5 — Run Compliance Check (API) and poll to terminal status.
    //
    // Same shape as Step 4. Compliance historically runs longer than DQ
    // (CLI-level regulatory scan), so its budget is 180s.
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 5: Starting Compliance run via API…');
    const complianceStartRes = await page.request.post('/api/v1/compliance/runs/', {
      headers: writeHeaders,
      data: { asset_id: assetId, dataset_id: datasetId, scan_mode: 'internal' },
    });
    if (!complianceStartRes.ok()) {
      // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
      const body = await complianceStartRes.text().catch(() => '');
      throw new Error(
        `Compliance run start failed: ${complianceStartRes.status()} — ${body.slice(0, 400)}`,
      );
    }
    const complianceRun = (await complianceStartRes.json()) as { id: string };
    console.log(`Compliance run started: ${complianceRun.id}`);

    const complianceTerminal = await pollRunTerminalStatus(
      page,
      'compliance/runs',
      complianceRun.id,
      { timeoutMs: 180_000, pollEveryMs: 3_000 },
    );
    test.skip(
      complianceTerminal === null,
      'Compliance worker did not finish the run within 180s — skip (PR 10 per-reason gate).',
    );
    if (complianceTerminal === null) return;
    console.log(`Compliance run ${complianceRun.id} → ${complianceTerminal}`);

    // ─────────────────────────────────────────────────────────────────
    // Step 6 — Confirm asset-level dq/compliance statuses are activation-ready
    //
    // The run-terminal handlers in hub/apps/dq/views.py:847-859 and
    // hub/apps/compliance/services.py:406-408 write these fields back
    // to the asset. Read them directly so a blocker from Step 7 gives a
    // clear diagnostic instead of the generic ASSET_ACTIVATION_BLOCKED
    // message.
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 6: Verifying asset-level dq/compliance statuses…');
    const preActivate = await verifyViaApi<{
      dq_status: string;
      compliance_status: string;
    }>(
      page,
      `/api/v1/assets/${assetId}/`,
      (body: { dq_status: string; compliance_status: string }) =>
        ['PASS', 'WARN'].includes(body.dq_status) &&
        ['PASS', 'WARN'].includes(body.compliance_status),
    );
    console.log(
      `Asset ${assetId} — dq_status=${preActivate.dq_status}, compliance_status=${preActivate.compliance_status}`,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 7 — Activate asset via UI
    // ─────────────────────────────────────────────────────────────────
    console.log('Step 7: Activating asset via UI…');
    await navigateToRouteFromApp(page, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, [data-testid="asset-detail-page"], .asset-detail-content, h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const activateAssetButton = page.locator('button:has-text("Activate Asset")');
    await activateAssetButton.waitFor({ state: 'visible', timeout: 15000 });
    await expect(activateAssetButton).toBeEnabled();

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
          `Step 6 confirmed preconditions at the API level — if this 4xx's, something ` +
          `mutated the asset/contract between Step 6 and Step 7 (concurrent test run? ` +
          `contract re-validation that flipped to ERROR?).`,
      );
    }

    // ─────────────────────────────────────────────────────────────────
    // Step 8 — Dual-channel confirmation: API ACTIVE + UI badge ACTIVE
    // ─────────────────────────────────────────────────────────────────
    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, { status: 'ACTIVE' });
    console.log(`Asset ${assetId} → ACTIVE (API-verified)`);

    await expect(page.locator('.status-badge').first()).toContainText('ACTIVE', {
      timeout: 15000,
    });
    console.log(`Asset ${assetId} → ACTIVE (UI-verified, with dataset + DQ + compliance)`);

    // ─────────────────────────────────────────────────────────────────
    // Step 9 — Regression guard: DQ score renders as a sensible percent
    //
    // Backend contract: hub/apps/dq/models.py:113 documents quality_score
    // as 0-100 (already a percentage). AssetDetailPage must render it
    // as-is, not multiply by 100 a second time. Historical bug: the
    // component had `Math.round(quality_score * 100)%` which produced
    // "Score: 10000%" for a fully-passing run — both in the
    // `.inline-summary-score` near the top of the page and in the
    // `.quality-score` entries within the Quality Gates list.
    //
    // Assert every rendered score on the page parses to an integer in
    // [0, 100]. Catches any future drift (unit mix-ups on new fields,
    // accidental reintroduction of the `* 100`) at the UI level where
    // it actually matters to users.
    // ─────────────────────────────────────────────────────────────────
    const scoreTexts = await page
      .locator('.inline-summary-score, .quality-score')
      .allTextContents();
    expect(
      scoreTexts.length,
      'Expected at least one rendered DQ/compliance score on the asset detail page after a SUCCEEDED run.',
    ).toBeGreaterThan(0);
    for (const raw of scoreTexts) {
      const match = raw.match(/(-?\d+(?:\.\d+)?)\s*%/);
      expect(
        match,
        `Rendered score text "${raw}" does not contain a "<number>%" token. ` +
          `If the format changed intentionally, update this regex.`,
      ).not.toBeNull();
      const value = Number(match![1]);
      expect(
        value,
        `Rendered score "${raw}" parsed to ${value}; expected an integer percent ` +
          `in [0, 100]. If this is >100, AssetDetailPage is multiplying quality_score ` +
          `by 100 again — backend contract (hub/apps/dq/models.py:113) is already 0-100.`,
      ).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(100);
    }
  });
});
