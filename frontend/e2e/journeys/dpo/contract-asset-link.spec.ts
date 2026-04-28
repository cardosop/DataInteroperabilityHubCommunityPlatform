/**
 * E2E Test: Contract-Asset Linking
 * Tests the "Linked Asset" section on ContractDetailPage and ODPSDetailPage.
 * Uses real backend (no mocks/stubs).
 */

import { expect, test } from '@playwright/test';
import {
  createODCSContractViaApi,
  createODPSContractLinkedToAssetViaApi,
  getContractLinkedAssetIdViaApi,
} from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Contract-Asset Linking', () => {
  test.setTimeout(120000);

  test('should display "Linked Asset" section on contract detail when asset_id is set', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    const contractId = await createODCSContractViaApi(testUser);
    const assetId = await getContractLinkedAssetIdViaApi(testUser, contractId);
    expect(assetId).toBeTruthy();

    await loginAndNavigateToRoute(page, testUser, `/contracts/${contractId}`, {
      timeout: 60000,
      contentSelector: '.contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"]', { timeout: 20000 });

    const linkedAsset = page.locator('[data-testid="contract-linked-asset"]');
    await expect(linkedAsset).toBeVisible({ timeout: 15000 });
    const viewBtn = page.locator('[data-testid="contract-linked-asset-view"]');
    await expect(viewBtn).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to asset detail when "View Asset" is clicked on contract page', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    const contractId = await createODCSContractViaApi(testUser);
    const assetId = await getContractLinkedAssetIdViaApi(testUser, contractId);
    expect(assetId).toBeTruthy();

    await loginAndNavigateToRoute(page, testUser, `/contracts/${contractId}`, {
      timeout: 60000,
      contentSelector: '.contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"]', { timeout: 20000 });

    const viewBtn = page.locator('[data-testid="contract-linked-asset-view"]');
    await viewBtn.click();
    await expect(page).toHaveURL(new RegExp(`/assets/${assetId}`), { timeout: 20000 });
    await waitForLoadingComplete(page, { timeout: 20000 });
    await page.waitForSelector('.asset-detail-page, [data-testid="asset-detail-page"], .error-display, [data-testid="error-display"]', { timeout: 20000 });
  });

  test('should display "Linked Asset" section on ODPS detail when asset_id is set', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    const odpsContractId = await createODPSContractLinkedToAssetViaApi(testUser);

    await loginAndNavigateToRoute(page, testUser, `/odps/${odpsContractId}`, {
      timeout: 60000,
      contentSelector: '.odps-detail-page, .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.odps-detail-page, .error-display, [data-testid="error-display"]', { timeout: 20000 });

    const linkedAsset = page.locator('[data-testid="odps-linked-asset"]');
    await expect(linkedAsset).toBeVisible({ timeout: 20000 });
    const viewBtn = page.locator('[data-testid="odps-linked-asset-view"]');
    await expect(viewBtn).toBeVisible({ timeout: 10000 });
  });

  test('should display contracts table with columns on asset detail page', async ({ page }) => {
    const testUser = await getTestUser();
    const contractId = await createODCSContractViaApi(testUser);
    const assetId = await getContractLinkedAssetIdViaApi(testUser, contractId);
    expect(assetId).toBeTruthy();

    await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, [data-testid="asset-detail-page"], .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page, [data-testid="asset-detail-page"], .error-display, [data-testid="error-display"]', { timeout: 20000 });

    const contractsSection = page.locator('[data-testid="asset-contracts-section"]');
    await expect(contractsSection).toBeVisible({ timeout: 10000 });

    const contractsTable = page.locator('[data-testid="contracts-table"]');
    await expect(contractsTable).toBeVisible({ timeout: 15000 });
    const headers = contractsTable.locator('thead th');
    const headerTexts = await headers.allTextContents();
    expect(headerTexts).toContain('Name');
    expect(headerTexts).toContain('Format');
    expect(headerTexts).toContain('Normalization');
    expect(headerTexts).toContain('Validation');
  });

  test('should display datasets table with columns on asset detail page', async ({ page }) => {
    const testUser = await getTestUser();
    const contractId = await createODCSContractViaApi(testUser);
    const assetId = await getContractLinkedAssetIdViaApi(testUser, contractId);
    expect(assetId).toBeTruthy();

    await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, [data-testid="asset-detail-page"], .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });
    await page.waitForSelector('.asset-detail-page, [data-testid="asset-detail-page"], .error-display, [data-testid="error-display"]', { timeout: 20000 });

    const datasetsSection = page.locator('[data-testid="asset-datasets-section"]');
    await expect(datasetsSection).toBeVisible({ timeout: 10000 });

    const datasetsTable = page.locator('[data-testid="datasets-table"]');
    await expect(datasetsTable).toBeVisible({ timeout: 15000 });
    const headers = datasetsTable.locator('thead th');
    const headerTexts = await headers.allTextContents();
    expect(headerTexts).toContain('Name');
    expect(headerTexts).toContain('Format');
    expect(headerTexts).toContain('Rows');
    expect(headerTexts).toContain('Size');
  });
});
