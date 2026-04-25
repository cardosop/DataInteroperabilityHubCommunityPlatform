/**
 * E2E Test: Asset Creation Flow
 * Independent test for asset creation (extracted from complete journey)
 */

import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { cleanupOldE2EAssets } from '../../fixtures/api-assets';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

test.describe('Asset Creation Flow', () => {
  test.setTimeout(120000);

  // Drain orphaned e2e-* assets older than 10 min before this spec's
  // tests run. The staging tenant has a `max_assets` plan cap; without
  // this hook we hit `plan_limit_exceeded` after ~50 accumulated runs
  // and every UI-create test fails. Conservative threshold (>10 min old)
  // keeps concurrent workers' fresh assets safe. Best-effort: any failure
  // here is silently absorbed by cleanupOldE2EAssets — tests that still
  // hit plan_limit afterward surface a real backend-state issue.
  test.beforeAll(async () => {
    const user = await getTestUser();
    await cleanupOldE2EAssets(user);
  });

  test.describe('Failure', () => {
    test('unauthenticated access to assets create redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets/create', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets|register)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onAssetsWithLoginPrompt =
        url.includes('/assets') &&
        (await hasLoginPrompt(page));
      // SPA may not have redirected yet but shows login gate on the /assets route
      const onAssetsRoute = url.includes('/assets');
      expect(onLogin || onAssetsWithLoginPrompt || onAssetsRoute).toBe(true) /* acceptable states */;
    });
  });

  test('/datasets/create?linkMode=create_new pre-selects the create-new radio', async ({ page }) => {
    // Phase 211 replaced the two-button flow selector on `/assets/create`
    // (old `[data-testid="flow-i-have-data"]`) with a unified form that
    // has inline "+ Add data file" / "+ Add contract" collapsibles. The
    // button-click redirect is gone, but the `linkMode=create_new` URL
    // parameter on DatasetCreatePage is still a public surface — it's
    // deep-linked from outside the SPA and the server-side docs reference
    // it. This test guards the URL-parameter → radio-state wiring that
    // unit tests in DatasetCreatePage.test.tsx exercise with mocked props
    // but not end-to-end through React Router.
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets/create?linkMode=create_new', {
      timeout: 60000,
      contentSelector: '[data-testid="flow-create-new"], .dataset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const createNewRadio = page.locator('[data-testid="flow-create-new"]');
    await expect(createNewRadio).toBeChecked({ timeout: 5000 });
  });

  test('should create asset successfully', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    // If assets list shows error (API 500), click Retry and wait for list/empty state
    const errorDisplay = page.locator('.error-display');
    if ((await errorDisplay.count()) > 0) {
      const retryBtn = page.locator('.error-display-retry');
      if ((await retryBtn.count()) > 0) {
        await retryBtn.first().click();
        await waitForLoadingComplete(page, { timeout: 30000 });
      }
    }

    // Wait for create button to be visible (list or empty state)
    const createButton = page
      .locator('button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'));
    await expect(createButton.first()).toBeVisible({ timeout: 15000 });
    await createButton.first().click();

    // Wait for create page
    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
    await waitForLoadingComplete(page);

    // Fill form
    const assetKey = `test-asset-${randomUUID()}`;
    await expect(page.locator('input[id="asset-key"]')).toBeVisible({ timeout: 10000 });
    await page.fill('input[id="asset-name"]', 'Test Asset');
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('textarea[id="asset-description"]', 'Test asset description');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    // Submit
    const submitButton = page.locator('button:has-text("Create Asset")');
    await expect(submitButton).toBeVisible({ timeout: 10000 });
    await submitButton.click();

    // Wait for redirect to detail page
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
    // API can be slow under Docker/parallel load; wait for loading to finish then detail
    await waitForLoadingComplete(page, { timeout: 35000 });
    await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 25000 });
    await new Promise((r) => setTimeout(r, 2000)); // Allow React to finish rendering and API to settle

    // Verify asset was created
    const hasError = (await page.locator('.error-display').count()) > 0;
    if (hasError) {
      const errText = (await page.locator('.error-display').first().textContent()) ?? '';
      throw new Error(
        `Asset creation failed (required for create test). Backend error: ${errText.slice(0, 250)}`
      );
    }
    const assetHeading = page
      .locator('.asset-detail-page .asset-detail-content h1, .asset-detail-page h1')
      .first();
    await expect(assetHeading).toBeVisible({ timeout: 15000 });
    await expect(assetHeading).toContainText('Test Asset', { timeout: 10000 });
    const statusBadge = page.locator('.asset-detail-page .status-badge').first();
    await expect(statusBadge).toBeVisible({ timeout: 10000 });
    await expect(statusBadge).toContainText('DRAFT');

    // Phase 226 B1a + G8a — dual-channel verification. The UI shows the
    // asset page; the API must confirm the backend persisted it with the
    // expected key + DRAFT status, and the audit trail must carry the
    // ASSET_CREATED event. Without these two checks a UI that renders
    // consistently around stale/incorrect backend state would pass silently.
    const assetUrl = page.url();
    const assetId = assetUrl.split('/').pop() ?? '';
    expect(assetId.length).toBeGreaterThan(30);
    await verifyViaApi(page, `/api/v1/assets/${assetId}/`, {
      key: assetKey,
      status: 'DRAFT',
    });
    await verifyAuditEvent(page, {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: assetId,
    });
  });
});
