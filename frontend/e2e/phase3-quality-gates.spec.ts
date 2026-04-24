/**
 * Phase 3 E2E Test — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-CPO-001 (Review Compliance for Asset), JOURNEY-DPO-001 (compliance/DQ steps).
 * EXCLUDED FROM CI: removed from batch 7 (2026-03-14). Run manually via: bash scripts/e2e-batches.sh 9
 * Prefer journey specs under journeys/cpo/ and journeys/dpo/. Deletion target: after sign-off.
 *
 * Tests DQ and Compliance quality gates: run compliance + DQ → handle fail → rerun → pass
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from './fixtures/auth';
import {
  loginAndNavigateToRoute,
  navigateToRouteFromApp,
} from './fixtures/helpers';
import { verifyViaApi } from './fixtures/verifyViaApi';

test.describe('Phase 3 Quality Gates', () => {
  test('complete journey: run compliance + DQ → handle fail → rerun → pass', async ({ page }) => {
    test.setTimeout(120000);

    // Login and navigate to assets
    const testUser = await getTestUser();
    console.log('Navigating to /assets');
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, .asset-list-header, h1',
    });
    console.log('Asset list page content found');

    await page.waitForTimeout(1000);

    // Find create button - could be in header, empty state, or list page (same as Phase 2)
    console.log('Looking for Create Asset button...');
    const createButton = page
      .locator('button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'))
      .first();
    try {
      await createButton.waitFor({ state: 'visible', timeout: 45000 });
    } catch {
      // Transient load/connection may delay content; retry page once
      console.log('Create Asset button not visible, reloading assets page...');
      await page.goto('/assets', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector(
        '.asset-list-page, .empty-state, .error-display, .asset-list-header, h1:has-text("Assets")',
        {
          timeout: 30000,
        }
      );
      await page.waitForTimeout(2000);
      await createButton.waitFor({ state: 'visible', timeout: 30000 });
    }
    console.log('Clicking Create Asset button...');
    await createButton.click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 30000 });
    console.log('On asset create page, URL:', page.url());

    // Wait for form to be ready
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    await page.waitForSelector('input[id="asset-key"]', { timeout: 30000 });
    console.log('Form inputs found');

    const assetKey = `test-asset-${Date.now()}`;
    await page.fill('input[id="asset-name"]', 'Test Asset for Quality Gates');
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('textarea[id="asset-description"]', 'Test asset for DQ and Compliance');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');
    console.log('Form filled');

    const submitButton = page.locator('button:has-text("Create Asset")');
    await submitButton.waitFor({ state: 'visible', timeout: 30000 });
    console.log('Submitting form...');

    const waitForAssetDetailRedirect = (timeoutMs: number) =>
      page.waitForURL(
        (url) => {
          const path = url.pathname;
          return path.startsWith('/assets/') && path !== '/assets/create' && path !== '/assets';
        },
        { timeout: timeoutMs, waitUntil: 'domcontentloaded' }
      );

    await submitButton.click();
    console.log('Waiting for redirect to asset detail...');
    try {
      await waitForAssetDetailRedirect(60000);
    } catch (e) {
      // Transient ERR_CONNECTION_RESET can prevent redirect; retry submit once
      if (page.url().includes('/assets/create')) {
        console.log('Redirect timed out (possible connection reset), retrying submit...');
        await page.waitForTimeout(3000);
        await submitButton.click();
        await waitForAssetDetailRedirect(45000);
      } else {
        throw e;
      }
    }
    if (page.url().includes('/assets/create')) {
      const errEl = await page.locator('.error-display').first().textContent().catch(() => '');
      const errHint = errEl ? ` Backend error: ${errEl.slice(0, 200)}` : '';
      throw new Error(`Asset creation redirect failed. Still on create page.${errHint}`);
    }

    const assetUrl = page.url();
    const pathParts = assetUrl.split('/');
    const assetId = pathParts[pathParts.length - 1];
    console.log('Asset created, ID:', assetId);

    // Validate it's a UUID format
    if (!assetId || assetId === 'create' || assetId.length < 30) {
      throw new Error(`Invalid asset ID extracted: ${assetId} from URL: ${assetUrl}`);
    }

    // Dual-channel verification (PR 7a-ext2 — second verifyViaApi adoption).
    // The URL regex above proves the UI routed to an asset detail page, but
    // not that the backend actually persisted the asset. A UI regression
    // that redirects on a 5xx would pass the URL check silently. Hit the
    // API directly and assert the record landed with the expected key +
    // DRAFT status before proceeding with the DQ / compliance flow that
    // depends on it.
    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
      key: assetKey,
      status: 'DRAFT',
    });

    // Wait for asset detail page to load
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    await page.waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 30000 });
    console.log('Asset detail page loaded');

    // Verify asset heading
    const assetHeading = page.locator('.asset-detail-page h1, .asset-detail-content h1').first();
    await expect(assetHeading).toContainText('Test Asset for Quality Gates', { timeout: 30000 });
    console.log('Asset heading verified');

    // Step 2: Upload File and Create Dataset — pre-linked to the asset
    // Using DatasetCreatePage "existing asset" linkMode so the dataset is created
    // pre-linked via POST /datasets/ {file_id, asset_id}. This replaces the older
    // flow (create unlinked dataset → attach via DatasetPicker) which required several
    // reloads and often exhausted the 120s test budget on remote staging.
    console.log('Navigating to dataset create page...');
    await navigateToRouteFromApp(page, '/datasets/create', {
      timeout: 30000,
      contentSelector: '.dataset-create-page',
    });
    await page.waitForSelector('.dataset-create-page, h1:has-text("Create Dataset")', {
      timeout: 30000,
    });
    console.log('Dataset create page loaded');

    // Switch to "Link to existing asset" linkMode
    console.log('Selecting "existing asset" linkMode...');
    await page.locator('[data-testid="flow-existing"]').check();

    // Pick the asset we just created via AssetPicker.
    // Backend searches name/key/description only (hub/apps/assets/views.py:67),
    // so we search by the unique assetKey (UUID prefix would not match).
    console.log('Selecting asset in AssetPicker...');
    const assetPicker = page.locator('[data-testid="asset-picker"]');
    await assetPicker.waitFor({ state: 'visible', timeout: 30000 });
    const assetPickerInput = assetPicker.locator('input[aria-label="Select asset"]');
    await assetPickerInput.click();
    await assetPickerInput.fill(assetKey);
    const assetOption = page.locator(`#asset-picker-option-${assetId}`);
    await assetOption.waitFor({ state: 'visible', timeout: 30000 });
    await assetOption.click();

    // Upload the file. `input[type="file"]` is always rendered inside FileUpload
    // (visually hidden) so setInputFiles works without needing a dropzone click.
    const phase3FileBase = `test-p3-qg-${Date.now()}`;
    console.log('Uploading file...');
    const datasetFileInput = page.locator('.dataset-create-page input[type="file"]');
    await datasetFileInput.waitFor({ state: 'attached', timeout: 30000 });
    await datasetFileInput.setInputFiles({
      name: `${phase3FileBase}.csv`,
      mimeType: 'text/csv',
      buffer: Buffer.from(
        'name,email,age\nJohn Doe,john@example.com,30\nJane Smith,jane@example.com,25'
      ),
    });
    console.log('File selected, waiting for upload to complete...');
    await page.waitForSelector('.file-upload-dropzone.upload-success', { timeout: 45000 });
    console.log('File upload completed');

    // Submit — button enables once both uploadedFile and selectedAssetId are set
    console.log('Clicking Create Dataset button...');
    const createDatasetButton = page.locator('[data-testid="btn-create-dataset"]');
    await expect(createDatasetButton).toBeEnabled({ timeout: 30000 });
    await createDatasetButton.click();

    // In 'existing' linkMode the app redirects to /datasets/{uuid}
    console.log('Waiting for redirect to dataset detail...');
    await page.waitForURL(
      /\/datasets\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
      { timeout: 45000 }
    );
    const datasetIdMatch = page.url().match(/\/datasets\/([0-9a-f-]+)$/i);
    const datasetId: string | null = datasetIdMatch ? datasetIdMatch[1] : null;
    console.log('Dataset created (pre-linked to asset), ID:', datasetId);

    // Step 3: Navigate back to asset detail page — dataset_id should already be
    // populated by get_dataset_id() since asset.datasets.first() is the new one.
    console.log('Navigating back to asset detail page...');
    try {
      await navigateToRouteFromApp(page, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
        user: testUser,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('Redirected to login') || msg.includes('Still on login')) {
        await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
          timeout: 60000,
          contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
        });
      } else {
        throw err;
      }
    }
    await page.waitForSelector('.asset-detail-page, .asset-detail-content, .error-display', {
      timeout: 45000,
    });
    console.log('Asset detail page loaded');

    // Step 4: Run DQ Check — dataset is pre-linked so button renders on first load.
    // `Run DQ Check` only renders when asset.dataset_id is set (see AssetDetailPage.tsx).
    console.log('Looking for Run DQ Check button...');
    await page.waitForSelector('.asset-quality-gates-section, .quality-gate-subsection', {
      timeout: 30000,
    });
    const finalDQButton = page.locator('button:has-text("Run DQ Check")');
    await finalDQButton.waitFor({ state: 'visible', timeout: 30000 });

    // Observe the POST /dq/runs/ response directly so we catch silent
    // mutation failures (e.g. 401/403/5xx) instead of waiting 45s for a
    // list item that will never render. The prior approach used
    // page.reload() as a fallback which could land on /login if the
    // mutation had triggered the API client's refresh-then-logout path
    // (shared/api/client.ts:300-322).
    console.log('Found Run DQ Check button, clicking...');
    const dqCreateResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes('/dq/runs/') &&
        resp.request().method() === 'POST',
      { timeout: 45000 },
    );
    await finalDQButton.click();
    const dqCreateResponse = await dqCreateResponsePromise;
    const dqCreateStatus = dqCreateResponse.status();
    if (dqCreateStatus !== 201) {
      const body = await dqCreateResponse.text().catch(() => '');
      throw new Error(
        `POST /dq/runs/ returned ${dqCreateStatus}. Body: ${body.slice(0, 400)}`,
      );
    }
    const dqRunCreated = (await dqCreateResponse.json()) as { id: string };
    const dqRunId = dqRunCreated.id;
    console.log('DQ run created, ID:', dqRunId);

    // Poll for DQ run completion via API directly — avoids page reloads
    // which could redirect to /login if a background refresh fails. Max
    // 60s before skipping (matches previous budget: 20 * 3s).
    console.log('Polling /dq/runs/{id}/ for terminal status...');
    let dqTerminalStatus: string | null = null;
    for (let i = 0; i < 20; i++) {
      await page.waitForTimeout(3000);
      const dqRun = await verifyViaApi<{ status: string }>(
        page,
        `/api/v1/dq/runs/${dqRunId}/`,
        {},
      );
      console.log(`DQ run status (attempt ${i + 1}): ${dqRun.status}`);
      if (dqRun.status === 'SUCCEEDED' || dqRun.status === 'FAILED') {
        dqTerminalStatus = dqRun.status;
        break;
      }
    }

    // Conditional skip so the per-reason skip-counter gate (PR 10) can
    // fail CI when DQ-worker-down skips cross the threshold.
    test.skip(
      dqTerminalStatus === null,
      'DQ runner backend did not process run within 60s — skip. DQ worker may not be running.',
    );
    if (dqTerminalStatus === null) {
      return;
    }
    console.log('DQ run completed with status:', dqTerminalStatus);

    // Navigate to the DQ run detail page for UI verification
    console.log('Navigating to DQ run detail page...');
    await navigateToRouteFromApp(page, `/dq/runs/${dqRunId}`, {
      timeout: 30000,
      contentSelector: '.dq-run-detail-page, .dq-run-detail-content, .error-display',
      user: testUser,
    });
    await page.waitForSelector('.dq-run-detail-page, .dq-run-detail-content', {
      timeout: 30000,
    });
    console.log('DQ run detail page loaded');

    // Verify DQ results are displayed (only if run succeeded).
    // The viewer renders 1 `.dq-results-summary` container with N
    // `.summary-card` children — assert the container is visible, not
    // an exact count.
    const dqResults = page.locator('.dq-results-viewer, .dq-run-results-section');
    if ((await dqResults.count()) > 0) {
      console.log('DQ results viewer found');
      const dqSummary = page.locator('.dq-results-summary').first();
      if ((await dqSummary.count()) > 0) {
        await expect(dqSummary).toBeVisible({ timeout: 5000 });
        console.log('DQ results summary found');
      } else {
        console.log('DQ results summary not yet rendered (may still be loading)');
      }
    } else {
      console.log('DQ results not yet available (run may still be processing)');
    }

    // Go back to asset
    console.log('Navigating back to asset detail...');
    await navigateToRouteFromApp(page, `/assets/${assetId}`, {
      timeout: 30000,
      contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
      user: testUser,
    });
    await page.waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 30000 });

    // Step 5: Run Compliance Check — same pattern as DQ: observe POST
    // response + poll via API, no page reloads (which can redirect to /login
    // if a background refresh fails).
    console.log('Looking for Run Compliance Check button...');
    const runComplianceButton = page.locator('button:has-text("Run Compliance Check")');
    await runComplianceButton.waitFor({ state: 'visible', timeout: 30000 });

    const complianceCreatePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes('/compliance/runs/') &&
        resp.request().method() === 'POST',
      { timeout: 45000 },
    );
    await runComplianceButton.click();
    const complianceCreateResponse = await complianceCreatePromise;
    const complianceCreateStatus = complianceCreateResponse.status();
    if (complianceCreateStatus !== 201) {
      const body = await complianceCreateResponse.text().catch(() => '');
      throw new Error(
        `POST /compliance/runs/ returned ${complianceCreateStatus}. Body: ${body.slice(0, 400)}`,
      );
    }
    const complianceRunCreated = (await complianceCreateResponse.json()) as { id: string };
    const complianceRunId = complianceRunCreated.id;
    console.log('Compliance run created, ID:', complianceRunId);

    // Poll for compliance terminal status via API (max 120s — compliance
    // typically runs longer than DQ).
    console.log('Polling /compliance/runs/{id}/ for terminal status...');
    let complianceTerminalStatus: string | null = null;
    for (let i = 0; i < 60; i++) {
      await page.waitForTimeout(2000);
      const complianceRun = await verifyViaApi<{ status: string }>(
        page,
        `/api/v1/compliance/runs/${complianceRunId}/`,
        {},
      );
      if (
        complianceRun.status === 'SUCCEEDED' ||
        complianceRun.status === 'FAILED'
      ) {
        complianceTerminalStatus = complianceRun.status;
        break;
      }
    }
    test.skip(
      complianceTerminalStatus === null,
      'Compliance runner backend did not process run within 120s — skip. Compliance worker may not be running.',
    );
    if (complianceTerminalStatus === null) {
      return;
    }
    console.log('Compliance run completed with status:', complianceTerminalStatus);

    // Navigate to the compliance run detail page for UI verification
    console.log('Navigating to compliance run detail page...');
    await navigateToRouteFromApp(page, `/compliance/runs/${complianceRunId}`, {
      timeout: 30000,
      contentSelector: '.compliance-run-detail-page, .compliance-run-detail-content, .error-display',
      user: testUser,
    });
    await page.waitForSelector(
      '.compliance-run-detail-page, .compliance-run-detail-content',
      { timeout: 30000 },
    );

    // If compliance failed, verify fail-closed UX on the detail page
    if (complianceTerminalStatus === 'FAILED') {
      const remediationSection = page.locator(
        '.compliance-results-remediation, .remediation-suggestions'
      );
      if ((await remediationSection.count()) > 0) {
        // `.remediation-item` is per-item in an N-item list; assert at least
        // one is visible, not an exact count.
        await expect(
          page.locator('.remediation-item, .remediation-suggestion').first()
        ).toBeVisible({ timeout: 5000 });
      }
      // At least one fail-closed warning must be visible (multiple are valid).
      await expect(page.locator('.fail-closed-warning, .blocked-warning').first()).toBeVisible({
        timeout: 5000,
      });
    } else {
      // Compliance passed — verify filtering UX is available.
      // The ComplianceRunResultsViewer renders Severity + Regulation filters
      // by design, so assert scoped visibility rather than an exact count.
      const filters = page.locator('.compliance-results-filters, .filter-group');
      if ((await filters.count()) > 0) {
        const complianceSelects = page.locator('.compliance-results-filters select');
        await expect(complianceSelects.first()).toBeVisible({ timeout: 5000 });
      }
    }

    // Step 6: back to asset detail; verify retry button present+enabled
    await navigateToRouteFromApp(page, `/assets/${assetId}`, {
      timeout: 30000,
      contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
      user: testUser,
    });
    await page.waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 30000 });
    const retryComplianceButton = page.locator('button:has-text("Run Compliance Check")');
    if ((await retryComplianceButton.count()) > 0) {
      await expect(retryComplianceButton).toBeEnabled();
    }

    // Step 7: Verify results viewers are usable at scale (filtering/severity grouping)
    // Test DQ results viewer filtering
    console.log('Navigating to DQ runs list page...');
    await page.goto('/dq');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const dqContentSelector = '.dq-run-list-page, .dq-run-list-table, .empty-state, .error-display';
    try {
      await page.waitForSelector(dqContentSelector, { timeout: 25000 });
    } catch {
      console.log('DQ page content wait timed out, retrying navigation...');
      await page.goto('/dq', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);
      await page.waitForSelector(dqContentSelector, { timeout: 45000 });
    }
    console.log('DQ runs list page loaded');

    // Verify filters are available
    const dqFilters = page.locator('.dq-run-list-filters select');
    if ((await dqFilters.count()) > 0) {
      // Test filtering by status
      await dqFilters.first().selectOption('SUCCEEDED');
      await page.waitForTimeout(1000);

      // Verify filtered results
      const filteredRows = page.locator('.dq-run-row');
      if ((await filteredRows.count()) > 0) {
        const firstRowStatus = await filteredRows.first().locator('.status-badge').textContent();
        expect(firstRowStatus).toContain('SUCCEEDED');
      }
    }

    // Test Compliance results viewer filtering
    console.log('Navigating to Compliance runs list page...');
    await page.goto('/compliance');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const complianceContentSelector =
      '.compliance-run-list-page, .compliance-run-list-table, .empty-state, .error-display';
    try {
      await page.waitForSelector(complianceContentSelector, { timeout: 25000 });
    } catch {
      // Transient connection reset may prevent load; retry navigation once
      console.log('Compliance page content wait timed out, retrying navigation...');
      await page.goto('/compliance', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);
      await page.waitForSelector(complianceContentSelector, { timeout: 45000 });
    }
    console.log('Compliance runs list page loaded');

    const complianceFilters = page.locator('.compliance-run-list-filters select');
    if ((await complianceFilters.count()) > 0) {
      // Test filtering by status
      await complianceFilters.first().selectOption('SUCCEEDED');
      await page.waitForTimeout(1000);

      // Verify filtered results
      const filteredRows = page.locator('.compliance-run-row');
      if ((await filteredRows.count()) > 0) {
        const firstRowStatus = await filteredRows.first().locator('.status-badge').textContent();
        expect(firstRowStatus).toContain('SUCCEEDED');
      }
    }

    console.log('Phase 3 E2E test completed successfully');
  });
});
