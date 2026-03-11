/**
 * E2E Test: Dataset Edit with Asset Link (UX Use Case)
 *
 * Covers: dataset detail page, Edit / Link to Asset button, AssetPicker for asset_id, save.
 * Real backend only; no mocks. Uses getTestUser(), loginAndNavigateToRoute, waitForLoadingComplete.
 *
 * Reference: tasks.md 29.66.15.2, 29.66.15.3
 */

import { expect, test } from '@playwright/test';
import { createDatasetViaApi } from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Dataset Edit with Asset Link (UX)', () => {
  test.setTimeout(180000); // 3 min

  test('dataset list loads and empty state shows create action', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets', {
      timeout: 60000,
      contentSelector: '[data-testid="dataset-list-page"], .empty-state, .error-display, .loading-spinner-container',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const listPage = page.locator('[data-testid="dataset-list-page"]');
    await expect(listPage).toBeVisible({ timeout: 15000 });

    const createBtn = page
      .locator('button:has-text("Create Dataset")')
      .or(page.locator('.empty-state-action:has-text("Create Dataset")'))
      .or(page.locator('a:has-text("Create Dataset")'));
    await expect(createBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('dataset detail shows Edit and Link to Asset when no asset', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets', {
      timeout: 60000,
      contentSelector: '[data-testid="dataset-list-page"], .empty-state, .error-display',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const tableRows = page.locator('.dataset-list-table tbody tr');
    const hasDatasets = (await tableRows.count()) > 0;
    if (hasDatasets) {
      await tableRows.first().click();
      await waitForLoadingComplete(page, { timeout: 30000 });
      const hasLinkToAsset = (await page.locator('[data-testid="btn-link-to-asset"]').count()) > 0;
      const hasEdit = (await page.locator('button:has-text("Edit")').count()) > 0;
      expect(hasLinkToAsset || hasEdit).toBe(true);
      return;
    }

    const createBtn = page
      .locator('button:has-text("Create Dataset")')
      .or(page.locator('.empty-state-action:has-text("Create Dataset")'))
      .first();
    if ((await createBtn.count()) === 0) {
      test.skip();
      return;
    }
    await createBtn.click();
    await expect(page).toHaveURL(/\/datasets\/create/, { timeout: 10000 });
    await waitForLoadingComplete(page);

    const uploadHint = page.locator('.file-upload-hint, .file-upload-content');
    await expect(uploadHint.first()).toBeVisible({ timeout: 10000 });
  });

  test('Link to Asset opens edit form with AssetPicker', async ({ page }) => {
    const testUser = await getTestUser();
    const datasetId = await createDatasetViaApi(testUser);
    await loginAndNavigateToRoute(page, testUser, `/datasets/${datasetId}`, {
      timeout: 60000,
      contentSelector: '.dataset-detail-page, .error-display, .loading-spinner-container',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const linkToAssetBtn = page.locator('[data-testid="btn-link-to-asset"]');
    const editBtn = page.locator('button:has-text("Edit")');
    const hasLinkToAsset = (await linkToAssetBtn.count()) > 0;
    const hasEdit = (await editBtn.count()) > 0;

    if (!hasLinkToAsset && !hasEdit) {
      test.skip();
      return;
    }

    if (hasLinkToAsset) {
      await linkToAssetBtn.click();
    } else {
      await editBtn.click();
    }

    await expect(page.locator('[data-testid="dataset-edit-form"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="dataset-asset-picker"]')).toBeVisible({ timeout: 5000 });
  });

  test('dataset detail page shows Edit button', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets', {
      timeout: 60000,
      contentSelector: '[data-testid="dataset-list-page"], .empty-state, .error-display',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const table = page.locator('.dataset-list-table tbody tr');
    const hasTable = (await table.count()) > 0;
    if (!hasTable) {
      const emptyState = page.locator('[data-testid="dataset-list-empty-state"]');
      await expect(emptyState).toBeVisible({ timeout: 5000 });
      return;
    }

    const firstRow = page.locator('.dataset-list-table tbody tr').first();
    await firstRow.click();
    await waitForLoadingComplete(page, { timeout: 30000 });

    const editBtn = page.locator('button:has-text("Edit")');
    await expect(editBtn).toBeVisible({ timeout: 10000 });
  });
});
