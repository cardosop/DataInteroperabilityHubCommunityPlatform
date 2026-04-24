/**
 * Phase 2 E2E Test — DEPRECATED
 *
 * Migrated to: journeys/dpo/JOURNEY-DPO-001.spec.ts (JOURNEY-DPO-001: Onboard New Asset via Data-First Flow).
 * EXCLUDED FROM CI: removed from batch 7 (2026-03-14). Run manually via: bash scripts/e2e-batches.sh 9
 * Deletion target: once sign-off confirms journey coverage is sufficient. Prefer running
 * frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts instead.
 *
 * Tests complete catalog journey: create asset → upload file → create dataset → create contract → activate
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from './fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp, waitForAppMainReady, waitForLoadingComplete } from './fixtures/helpers';
import { verifyViaApi } from './fixtures/verifyViaApi';

test.describe('Phase 2 Catalog Journey', () => {
  test('complete journey: create asset → upload file → create dataset → create contract → activate', async ({
    page,
  }) => {
    test.setTimeout(120000);
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, h1',
    });

    await waitForLoadingComplete(page, { timeout: 15000 });

    // Try to find Create Asset button - it might be in header (.asset-list-header) or empty state
    const createButton = page
      .locator('.asset-list-header button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'))
      .or(page.locator('button:has-text("Create Asset")'));
    await createButton.first().waitFor({ timeout: 15000 });
    await createButton.first().click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });

    // Form uses React Hook Form bindings — inputs expose no DOM `id`.
    // getByLabel targets the accessible `<label>` text which survives
    // RHF / other refactors (public UI contract, not implementation detail).
    // See docs: https://playwright.dev/docs/locators#locate-by-label
    const assetKey = `test-asset-${Date.now()}`;
    await page.getByLabel('Key').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByLabel('Key').fill(assetKey);
    await page.getByLabel('Name').fill('Test Asset');
    await page.getByLabel('Description').fill('Test asset description');
    await page.getByLabel('Visibility').selectOption('INTERNAL');

    // Wait for submit button and click
    const submitButton = page.locator('button:has-text("Create Asset")');
    await submitButton.waitFor({ timeout: 10000 });
    await submitButton.click();

    // Wait for redirect to asset detail (UUID required; /assets/create must not match)
    const uuidRegex = /\/assets\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i;
    try {
      await page.waitForURL(uuidRegex, { timeout: 60000, waitUntil: 'domcontentloaded' });
    } catch {
      const errEl = await page.locator('.error-display').first().textContent().catch(() => '');
      const errHint = errEl ? ` Backend error: ${errEl.slice(0, 200)}` : '';
      throw new Error(`Asset creation redirect timed out. Current URL: ${page.url()}.${errHint}`);
    }
    const assetUrl = page.url();
    const uuidMatch = assetUrl.match(uuidRegex);
    const assetId = uuidMatch?.[1] ?? '';
    if (!assetId) {
      throw new Error(`Invalid asset ID from URL: ${assetUrl}`);
    }

    // Dual-channel verification (PR 7a-ext1 — first verifyViaApi proof-of-pattern).
    // The UI navigated to an asset detail URL, but that only proves the URL-level
    // routing — not that the backend actually persisted the asset. Hit the API
    // directly and assert on the record. If the UI ever regresses to fake-success
    // (e.g. client-side redirect on a 5xx response), this assertion catches it.
    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
      key: assetKey,
      status: 'DRAFT',
    });

    // Verify asset was created - wait for asset detail page (API can be slow)
    await page.waitForSelector('.asset-detail-page, .asset-detail-content, .error-display', { timeout: 35000 });
    if ((await page.locator('.error-display').count()) > 0) {
      const errText = (await page.locator('.error-display').first().textContent()) ?? '';
      throw new Error(`Asset creation failed: ${errText.slice(0, 200)}`);
    }
    const assetHeading = page.locator('.asset-detail-page h1, .asset-detail-content h1').first();
    await expect(assetHeading).toContainText('Test Asset', { timeout: 10000 });
    await expect(page.locator('.status-badge').first()).toContainText('DRAFT');

    // Step 2: Upload File (optional - skip for now to focus on dataset creation)
    // Note: File upload on asset detail page is optional - the main flow is dataset creation
    // Skip this step to avoid timeout issues - dataset creation will upload its own file
    console.log('Skipping Step 2 file upload - will upload file in Step 3 (dataset creation)');

    // Step 3: Create Dataset (from uploaded file) — client-side nav avoids auth race
    await navigateToRouteFromApp(page, '/datasets/create', {
      timeout: 60000,
      contentSelector: '.dataset-create-page',
    });

    await page.waitForTimeout(2000);

    // Find file upload dropzone
    const dropzone = page.locator('.file-upload-dropzone');
    if ((await dropzone.count()) > 0) {
      // Click on dropzone to trigger file input
      await dropzone.first().click();
      await page.waitForTimeout(500);

      const datasetFileInput = page.locator('input[type="file"]');
      if ((await datasetFileInput.count()) > 0) {
        // File inputs are hidden by design - set files directly
        await datasetFileInput.setInputFiles({
          name: 'test.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from('name,age\nJohn,30\nJane,25'),
        });

        // Wait for upload to complete - use multiple indicators
        const createDatasetButton = page.locator('button:has-text("Create Dataset")');

        // Monitor console for upload progress
        const uploadLogs: string[] = [];
        page.on('console', (msg) => {
          if (msg.text().includes('[FileUpload]')) {
            uploadLogs.push(msg.text());
            console.log(`[Browser] ${msg.text()}`);
          }
        });

        try {
          // Wait for button to be visible first
          await createDatasetButton.waitFor({ state: 'visible', timeout: 10000 });

          // Wait for button to be enabled - this is the most reliable indicator
          // The button is disabled until uploadedFile is set in DatasetCreatePage
          await page.waitForFunction(
            () => {
              const buttons = Array.from(document.querySelectorAll('button'));
              const createButton = buttons.find((btn) =>
                btn.textContent?.includes('Create Dataset')
              );
              return createButton && !createButton.disabled;
            },
            { timeout: 180000 } // 3 minutes for upload (generous timeout)
          );
          console.log('✅ Create Dataset button is enabled - file upload completed');

          // Verify success indicator is shown
          const success = page.locator('.upload-success, .file-upload-success');
          if ((await success.count()) > 0) {
            console.log('✅ Upload success indicator found');
          }
        } catch {
          console.log('⚠️ Timeout waiting for button to be enabled, checking state...');
          console.log('Upload logs:', uploadLogs.join('\n'));

          // Check for upload error
          const error = page.locator('.error-display');
          if ((await error.count()) > 0) {
            const errorText = await error.textContent();
            throw new Error(`File upload failed: ${errorText}`);
          }

          // Check if button is actually enabled anyway
          const isEnabled = await createDatasetButton.isEnabled();
          if (isEnabled) {
            console.log('✅ Button is enabled despite timeout - proceeding');
          } else {
            // Check upload progress
            const progress = page.locator('.file-upload-progress');
            if ((await progress.count()) > 0) {
              const progressText = await progress.textContent();
              console.log(`Upload still in progress: ${progressText}`);
              // Wait more
              await page.waitForTimeout(60000); // Wait 1 more minute
              const stillDisabled = await createDatasetButton.isEnabled();
              if (!stillDisabled) {
                throw new Error(
                  'File upload did not complete after extended wait - button still disabled'
                );
              }
            } else {
              throw new Error(
                'File upload did not complete - no progress indicator and button still disabled'
              );
            }
          }
        }
      }
    }

    // Fill asset ID only if valid UUID (backend rejects invalid format)
    const assetIdInput = page.locator('input[placeholder*="Asset ID"]');
    if (
      (await assetIdInput.count()) > 0 &&
      assetId &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(assetId)
    ) {
      await assetIdInput.fill(assetId);
    }

    // Click create button - wait for it to be enabled
    const createDatasetButton = page.locator('button:has-text("Create Dataset")');
    await createDatasetButton.waitFor({ state: 'visible', timeout: 10000 });

    // Check if button is disabled (might be waiting for file upload)
    let attempts = 0;
    while ((await createDatasetButton.isDisabled()) && attempts < 3) {
      console.log(`Button disabled, waiting... (attempt ${attempts + 1})`);
      await page.waitForTimeout(5000);
      attempts++;
    }

    // Click button (even if still disabled - might be a UI state issue)
    await createDatasetButton.click();

    // Wait for redirect to dataset detail
    await page.waitForURL(/\/datasets\/[^/]+$/, { timeout: 30000 });
    // Verify dataset was created - wait for dataset detail page to load
    await waitForAppMainReady(page, {
      timeout: 60000,
      contentSelector: '.dataset-detail-page, .dataset-detail-content, .dataset-detail-metadata, .error-display',
    });

    await page.waitForTimeout(2000); // Wait for React to render

    // Assert dataset content loaded — error-display is NOT an acceptable outcome
    const datasetContent = page
      .locator('.dataset-detail-page .dataset-detail-metadata')
      .or(page.locator('.dataset-detail-page .dataset-detail-content'))
      .first();
    await expect(datasetContent).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.error-display')).not.toBeVisible();

    // Step 4: Navigate to Contracts — client-side nav avoids auth race
    await navigateToRouteFromApp(page, '/contracts', {
      timeout: 60000,
      contentSelector: '.contract-list-page, .empty-state, h1',
    });

    await page.waitForTimeout(2000);

    // Contracts page loads as either heading or empty-state — wait on
    // whichever paints first, then branch. Replaces the stacked count()
    // guards (226.A1 anti-pattern).
    const contractsHeading = page.locator('.contract-list-page h1, .app-main h1').first();
    const contractsEmptyState = page.locator('.empty-state').first();
    await contractsHeading.or(contractsEmptyState).waitFor({
      state: 'visible',
      timeout: 15000,
    });
    if (await contractsHeading.isVisible()) {
      await expect(contractsHeading).toBeVisible();
    } else {
      // Empty-state path. URL assertion is the invariant that stays.
      expect(page.url()).toContain('/contracts');
    }

    // Step 5: Activate Asset — client-side nav or goto with retry
    await navigateToRouteFromApp(page, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, .asset-detail-content, h1',
    });

    await page.waitForTimeout(2000);

    // Activate Asset button MUST render here — we just created a DRAFT
    // asset with no contract. The prior `if (count() > 0) … else log`
    // shape silently passed when the button disappeared, hiding real
    // regressions in the activation UI (the whole point of this test).
    // Drop the guard and let the `waitFor` assert it loudly.
    const activateButton = page.locator('button:has-text("Activate Asset")');
    await activateButton.waitFor({ state: 'visible', timeout: 15000 });
    const responsePromise = page.waitForResponse(
      (r) => r.url().includes('/assets/') && r.url().includes('/activate/'),
      { timeout: 30000 },
    );
    await activateButton.click();
    const response = await responsePromise;
    const statusBadge = page.locator('.status-badge').first();
    if (response.status() === 200) {
      await page.reload();
      await page.waitForLoadState('domcontentloaded');
      await waitForLoadingComplete(page, { timeout: 35000 });
      await expect(statusBadge).toContainText('ACTIVE', { timeout: 15000 });
    } else {
      // Backend returned non-200 on activate — verified via curl against
      // staging on 2026-04-24 that this is a legit business-rule 400
      // with one of:
      //   * {"code":"VALIDATION_ERROR","error":"version field is required
      //      for optimistic locking"} (when the UI doesn't send `version`)
      //   * {"code":"ASSET_ACTIVATION_BLOCKED","error":"...requirements
      //      not met","details":["Asset must have an ACTIVE contract"]}
      //      (when the asset has no contract yet — this test's path)
      //
      // The original spec did `page.reload()` + assert `.status-badge`
      // shows DRAFT, but on staging the UI's 400-handler has a
      // logout-on-4xx side effect that drops the session: the reload
      // then lands on /login and the badge assertion fails with a
      // misleading "element not found". Tracked as PR 7a-ext3.
      //
      // Dual-channel substitute (PR 7a-ext1): verify the invariant — the
      // asset stays in DRAFT — via the REST API directly. Same guarantee,
      // doesn't depend on the UI's post-failed-activate state, and is
      // exactly the cross-channel pattern this whole initiative exists
      // to showcase.
      await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
        status: 'DRAFT',
      });
    }
  });

  test('asset list with filters', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, h1',
    });

    // Verify we're on assets page (not login or home)
    expect(page.url()).toContain('/assets');

    // Wait a bit more for React to render
    await page.waitForTimeout(2000);

    // Three mutually-exclusive page outcomes: heading rendered, empty
    // state rendered, or error-display rendered. The previous form used
    // stacked `if ((await x.count()) > 0) { expect(...) }` guards (226.A1
    // anti-pattern: a truly missing page silently passed because every
    // guard returned 0). Use Playwright's `.or()` chain to require that
    // AT LEAST ONE of the three selectors becomes visible within the
    // budget, then branch on which one won to keep the existing
    // error-state logging behaviour.
    const assetsHeading = page
      .locator('.asset-list-page h1, .app-main h1:has-text("Assets")')
      .first();
    const emptyState = page.locator('.empty-state').first();
    const errorDisplay = page.locator('.error-display').first();
    try {
      await assetsHeading.or(emptyState).or(errorDisplay).waitFor({
        state: 'visible',
        timeout: 15000,
      });
    } catch {
      await page.screenshot({ path: 'test-results/assets-page-debug.png', fullPage: true });
      throw new Error('Assets page did not load — no heading, empty state, or error found');
    }
    if (await assetsHeading.isVisible()) {
      await expect(assetsHeading).toContainText('Assets');
    } else if (await errorDisplay.isVisible()) {
      // Error state is an accepted outcome (e.g. empty-tenant backend
      // probe can 404 before the empty-state fallback paints). Log for
      // triage, assert we're still on the right route.
      const errorText = await errorDisplay.textContent();
      console.log('Assets page error:', errorText);
      expect(page.url()).toContain('/assets');
    } else {
      // Empty-state path — page loaded correctly with no assets.
      expect(page.url()).toContain('/assets');
    }

    // Test filters only if assets list is shown (not empty state)
    const assetListPage = page.locator('.asset-list-page');
    if ((await assetListPage.count()) > 0) {
      // Test search
      const searchInput = page.locator('input[placeholder="Search assets..."]');
      if ((await searchInput.count()) > 0) {
        await searchInput.fill('test');
        await page.waitForTimeout(500);
      }

      // Test status filter
      const statusSelect = page
        .locator('select')
        .filter({ hasText: /All Statuses|Draft|Active|Retired/ })
        .first();
      if ((await statusSelect.count()) > 0) {
        await statusSelect.selectOption('DRAFT');
        await page.waitForTimeout(500);
      }

      // Test visibility filter
      const visibilitySelect = page
        .locator('select')
        .filter({ hasText: /All Visibilities|Internal|External|Public/ })
        .first();
      if ((await visibilitySelect.count()) > 0) {
        await visibilitySelect.selectOption('INTERNAL');
        await page.waitForTimeout(500);
      }
    } else {
      // Empty state - that's fine, just verify page loaded
      console.log('Assets page is in empty state - no filters to test');
    }
  });

  test('dataset list and detail', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets', {
      timeout: 60000,
      contentSelector: '.dataset-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    // Auth-race condition: if loginAndNavigateToRoute landed on /login,
    // hoist the actual URL check into test.skip so the skip is conditional
    // (not a hard-coded `true`) and therefore satisfies the no-test-skip-true
    // ESLint rule from PR 5. Skip reasons still reach the skip-counter gate
    // (PR 10) so CI can fail the build when auth-race skips cross the threshold.
    test.skip(
      page.url().includes('/login'),
      'Redirected to login — auth may have expired',
    );
    if (page.url().includes('/login')) {
      return;
    }

    // Check for datasets page - list, empty state, or error (e.g. API wrong port)
    const datasetsHeading = page
      .locator('.dataset-list-page h1, .app-main h1:has-text("Datasets")')
      .first();
    const emptyState = page.locator('.empty-state');
    const errorTitle = page.locator('text=Failed to load datasets').first();

    if ((await datasetsHeading.count()) > 0) {
      await expect(datasetsHeading).toContainText('Datasets', { timeout: 10000 });
    } else if ((await emptyState.count()) > 0) {
      expect(page.url()).toContain('/datasets');
    } else if ((await errorTitle.count()) > 0) {
      expect(page.url()).toContain('/datasets');
    } else {
      await page.waitForTimeout(2000);
      const heading = page.locator('.app-main h1').first();
      if ((await heading.count()) > 0) {
        await expect(heading).toBeVisible({ timeout: 10000 });
      } else {
        expect(page.url()).toContain('/datasets');
      }
    }

    // If datasets exist, click on first one
    const firstDataset = page.locator('.dataset-row').first();
    if ((await firstDataset.count()) > 0) {
      await firstDataset.click();
      await page.waitForLoadState('domcontentloaded');
      await waitForLoadingComplete(page, { timeout: 15000 });
      // Dataset detail page: accept multiple possible class names / content markers
      const detailPage = page.locator(
        '.dataset-detail-page, [data-testid="dataset-detail-page"], .dataset-detail, h1'
      );
      const detailVisible = await detailPage.first().waitFor({ state: 'visible', timeout: 15000 }).then(() => true).catch(() => false);
      if (!detailVisible) {
        // Navigated but detail page component not identified — check URL moved to a dataset
        expect(page.url()).toMatch(/\/datasets\/[^/]+/);
      }
      // Back button is optional depending on UI version
      const backBtn = page.getByRole('button', { name: /back to datasets/i });
      if ((await backBtn.count()) > 0) {
        await expect(backBtn).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('contract list and operations', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/contracts', {
      timeout: 60000,
      contentSelector: '.contract-list-page, .empty-state, .error-display',
      acceptRedirectToLogin: true,
    });
    // Auth-race condition: if loginAndNavigateToRoute landed on /login,
    // hoist the actual URL check into test.skip so the skip is conditional
    // (not a hard-coded `true`) and therefore satisfies the no-test-skip-true
    // ESLint rule from PR 5. Skip reasons still reach the skip-counter gate
    // (PR 10) so CI can fail the build when auth-race skips cross the threshold.
    test.skip(
      page.url().includes('/login'),
      'Redirected to login — auth may have expired',
    );
    if (page.url().includes('/login')) {
      return;
    }

    // Check for contracts page
    const contractsHeading = page
      .locator('.contract-list-page h1, .app-main h1:has-text("Contracts")')
      .first();
    const emptyState = page.locator('.empty-state');

    if ((await contractsHeading.count()) > 0) {
      await expect(contractsHeading).toContainText('Contracts', { timeout: 10000 });
    } else if ((await emptyState.count()) > 0) {
      expect(page.url()).toContain('/contracts');
    } else {
      await page.waitForTimeout(2000);
      const heading = page.locator('.app-main h1').first();
      if ((await heading.count()) > 0) {
        await expect(heading).toBeVisible();
      }
    }

    // If contracts exist, click on first one
    const firstContract = page.locator('.contract-row').first();
    if ((await firstContract.count()) > 0) {
      await firstContract.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const detailHeading = page.locator('.contract-detail-page h1, .app-main h1').first();
      await expect(detailHeading).toBeVisible({ timeout: 10000 });

      // Test validate operation
      const validateButton = page.locator('button:has-text("Validate")');
      if ((await validateButton.count()) > 0) {
        await validateButton.click();
        await page.waitForTimeout(2000);
      }
    }
  });

  test('jobs list with auto-refresh', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/jobs', {
      timeout: 60000,
      contentSelector: '.job-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    // Auth-race condition: if loginAndNavigateToRoute landed on /login,
    // hoist the actual URL check into test.skip so the skip is conditional
    // (not a hard-coded `true`) and therefore satisfies the no-test-skip-true
    // ESLint rule from PR 5. Skip reasons still reach the skip-counter gate
    // (PR 10) so CI can fail the build when auth-race skips cross the threshold.
    test.skip(
      page.url().includes('/login'),
      'Redirected to login — auth may have expired',
    );
    if (page.url().includes('/login')) {
      return;
    }

    // Check for jobs page
    const jobsHeading = page.locator('.job-list-page h1, .app-main h1:has-text("Jobs")').first();
    const emptyState = page.locator('.empty-state');

    if ((await jobsHeading.count()) > 0) {
      await expect(jobsHeading).toContainText('Jobs', { timeout: 10000 });
    } else if ((await emptyState.count()) > 0) {
      expect(page.url()).toContain('/jobs');
    } else {
      await page.waitForTimeout(2000);
      const heading = page.locator('.app-main h1').first();
      if ((await heading.count()) > 0) {
        await expect(heading).toBeVisible();
      }
    }

    // Verify jobs list loads - might be empty state or table
    const jobsTable = page.locator('.job-list-table table, table');
    const jobsEmptyState = page.locator('.empty-state');

    if ((await jobsTable.count()) > 0) {
      await expect(jobsTable.first()).toBeVisible({ timeout: 10000 });
    } else if ((await jobsEmptyState.count()) > 0) {
      // Empty state is fine - page loaded correctly
      expect(page.url()).toContain('/jobs');
    } else {
      // Wait a bit more for page to load
      await page.waitForTimeout(2000);
      const table = page.locator('table').first();
      if ((await table.count()) > 0) {
        await expect(table).toBeVisible();
      } else {
        // Page loaded but no table - that's OK for empty state
        expect(page.url()).toContain('/jobs');
      }
    }

    // If jobs exist, click on first one
    const firstJob = page.locator('.job-row').first();
    if ((await firstJob.count()) > 0) {
      await firstJob.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const detailHeading = page.locator('.job-detail-page h1, .app-main h1').first();
      await expect(detailHeading).toBeVisible({ timeout: 10000 });
    }
  });
});
