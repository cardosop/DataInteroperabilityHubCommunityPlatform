/**
 * E2E Test: Onboarding Checklist & Activation Blocker Dialog
 * Tests the 6-step checklist shown on DRAFT assets and the activation blocker dialog.
 * Uses real backend (no mocks/stubs).
 */

import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import {
  createAssetViaApi,
  createODCSContractViaApi,
  getContractLinkedAssetIdViaApi,
} from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Onboarding Checklist', () => {
  test.setTimeout(180000);

  test('should display onboarding checklist on a DRAFT asset', async ({ page }) => {
    const testUser = await getTestUser();

    // Create a new asset via the UI
    await loginAndNavigateToRoute(page, testUser, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-checklist-${randomUUID()}`;
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('input[id="asset-name"]', 'Checklist Test Asset');
    await page.fill('textarea[id="asset-description"]', 'E2E onboarding checklist test');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    const submitButton = page.locator('button:has-text("Create Asset")');
    await expect(submitButton).toBeVisible({ timeout: 10000 });
    await submitButton.click();

    // Wait for redirect to detail page
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 20000 });

    // Verify the onboarding checklist is visible
    const checklist = page.locator('[data-testid="onboarding-checklist"]');
    await expect(checklist).toBeVisible({ timeout: 15000 });

    const progress = page.locator('[data-testid="onboarding-progress"]');
    await expect(progress).toContainText('1/6', { timeout: 10000 });

    // Verify all 6 steps are rendered
    const steps = page.locator('[data-testid="onboarding-steps"] li');
    await expect(steps).toHaveCount(6, { timeout: 10000 });

    // Step 1 should be completed
    const step1 = page.locator('[data-testid="onboarding-step-create-asset"]');
    await expect(step1).toHaveClass(/completed/, { timeout: 5000 });

    // Step 2 should be pending (no contract)
    const step2 = page.locator('[data-testid="onboarding-step-attach-contract"]');
    await expect(step2).toHaveClass(/pending/, { timeout: 5000 });
  });

  test('should show "Attach Contract" action on step 2 when no contract linked', async ({
    page,
  }) => {
    const testUser = await getTestUser();

    // Create asset
    await loginAndNavigateToRoute(page, testUser, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-action-${randomUUID()}`;
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('input[id="asset-name"]', 'Action Test Asset');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    await page.locator('button:has-text("Create Asset")').click();
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('[data-testid="onboarding-checklist"]', { timeout: 20000 });

    // Verify "Attach Contract" action button exists
    const action = page.locator('[data-testid="onboarding-action-attach-contract"]');
    await expect(action).toBeVisible({ timeout: 10000 });
  });

  test('should NOT display checklist on ACTIVE assets', async ({ page }) => {
    const testUser = await getTestUser();
    const activeAssetId = await createAssetViaApi(testUser, { ensureActivated: true });

    await loginAndNavigateToRoute(page, testUser, `/assets/${activeAssetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, .error-display, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 20000 });

    const checklist = page.locator('[data-testid="onboarding-checklist"]');
    await expect(checklist).toHaveCount(0, { timeout: 10000 });
  });

  test('should display activation blocker dialog when activation fails', async ({ page }) => {
    const testUser = await getTestUser();

    // Create a fresh DRAFT asset (no contract, no dataset)
    await loginAndNavigateToRoute(page, testUser, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-blocker-${randomUUID()}`;
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('input[id="asset-name"]', 'Blocker Test Asset');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    await page.locator('button:has-text("Create Asset")').click();
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page', { timeout: 20000 });

    // Click Activate — should be blocked
    const activateBtn = page.locator('[data-testid="btn-activate-asset"]');
    await expect(activateBtn).toBeVisible({ timeout: 10000 });
    await activateBtn.click();

    // Wait for the blocker dialog to appear
    const dialog = page.locator('[data-testid="activation-blocker-dialog"]');
    await expect(dialog).toBeVisible({ timeout: 15000 });

    // Verify blocker list is populated
    const blockerList = page.locator('[data-testid="activation-blocker-list"]');
    await expect(blockerList).toBeVisible({ timeout: 5000 });
    const items = blockerList.locator('li');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);

    // Should mention contract requirement
    const firstItemText = await items.first().textContent();
    expect(firstItemText?.toLowerCase()).toContain('contract');
  });

  test('should dismiss blocker dialog when Close button is clicked', async ({ page }) => {
    const testUser = await getTestUser();

    await loginAndNavigateToRoute(page, testUser, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-dismiss-${randomUUID()}`;
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('input[id="asset-name"]', 'Dismiss Test Asset');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    await page.locator('button:has-text("Create Asset")').click();
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page', { timeout: 20000 });

    // Trigger activation
    const activateBtn = page.locator('[data-testid="btn-activate-asset"]');
    await expect(activateBtn).toBeVisible({ timeout: 10000 });
    await activateBtn.click();

    // Wait for dialog
    const dialog = page.locator('[data-testid="activation-blocker-dialog"]');
    await expect(dialog).toBeVisible({ timeout: 15000 });

    // Dismiss
    const closeBtn = page.locator('[data-testid="blocker-dismiss"]');
    await closeBtn.click();

    // Dialog should disappear
    await expect(dialog).toHaveCount(0, { timeout: 5000 });
  });

  test('should display plural contracts table when contracts are linked', async ({ page }) => {
    const testUser = await getTestUser();
    const contractId = await createODCSContractViaApi(testUser);
    const assetId = await getContractLinkedAssetIdViaApi(testUser, contractId);
    expect(assetId).toBeTruthy();

    await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, .error-display, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 20000 });

    const contractsSection = page.locator('[data-testid="asset-contracts-section"]');
    await expect(contractsSection).toBeVisible({ timeout: 10000 });

    const datasetsSection = page.locator('[data-testid="asset-datasets-section"]');
    await expect(datasetsSection).toBeVisible({ timeout: 10000 });

    const contractsTable = page.locator('[data-testid="contracts-table"]');
    await expect(contractsTable).toBeVisible({ timeout: 15000 });
  });

  test('should display inline DQ summary section', async ({ page }) => {
    const testUser = await getTestUser();
    const assetId = await createAssetViaApi(testUser);

    await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, .error-display, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 20000 });

    const dqSummary = page.locator('[data-testid="asset-dq-summary"]');
    await expect(dqSummary).toBeVisible({ timeout: 10000 });

    const complianceSummary = page.locator('[data-testid="asset-compliance-summary"]');
    await expect(complianceSummary).toBeVisible({ timeout: 10000 });
  });

  test('should display progress bar with visual fill', async ({ page }) => {
    const testUser = await getTestUser();

    await loginAndNavigateToRoute(page, testUser, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-bar-${randomUUID()}`;
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('input[id="asset-name"]', 'Bar Test Asset');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    await page.locator('button:has-text("Create Asset")').click();
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('[data-testid="onboarding-checklist"]', { timeout: 20000 });

    const progressBar = page.locator('[data-testid="onboarding-progress-bar"]');
    await expect(progressBar).toBeVisible({ timeout: 5000 });
    const width = await progressBar.evaluate((el) => el.style.width);
    expect(width).toBe('17%');
  });

  test('should show upload section data-testid for file upload scroll target', async ({
    page,
  }) => {
    const testUser = await getTestUser();

    await loginAndNavigateToRoute(page, testUser, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-upload-${randomUUID()}`;
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('input[id="asset-name"]', 'Upload Section Test');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    await page.locator('button:has-text("Create Asset")').click();
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page', { timeout: 20000 });

    const uploadSection = page.locator('[data-testid="asset-upload-section"]');
    await expect(uploadSection).toBeVisible({ timeout: 10000 });
  });
});
