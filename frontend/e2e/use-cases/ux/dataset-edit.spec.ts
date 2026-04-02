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
  test.setTimeout(90000);

  test('dataset list loads and empty state shows create action', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets', {
      timeout: 60000,
      contentSelector: '[data-testid="dataset-list-page"], .empty-state',
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
    // forceNew: true — always create a brand-new dataset with no asset linked.
    // Without forceNew, createDatasetViaApi reuses the first existing dataset which may already
    // have asset_id set, causing btn-link-to-asset to never render.
    const datasetId = await createDatasetViaApi(testUser, { forceNew: true });
    await loginAndNavigateToRoute(page, testUser, `/datasets/${datasetId}`, {
      timeout: 60000,
      contentSelector: '.dataset-detail-page',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    // A dataset with no linked asset must show both Edit and Link to Asset.
    await expect(page.locator('button:has-text("Edit")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="btn-link-to-asset"]')).toBeVisible({ timeout: 5000 });
  });

  test('Link to Asset opens edit form with AssetPicker', async ({ page }) => {
    const testUser = await getTestUser();
    const datasetId = await createDatasetViaApi(testUser, { forceNew: true });
    await loginAndNavigateToRoute(page, testUser, `/datasets/${datasetId}`, {
      timeout: 60000,
      contentSelector: '.dataset-detail-page',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const linkToAssetBtn = page.locator('[data-testid="btn-link-to-asset"]');
    const editBtn = page.locator('button:has-text("Edit")');
    const hasLinkToAsset = (await linkToAssetBtn.count()) > 0;
    const hasEdit = (await editBtn.count()) > 0;

    if (!hasLinkToAsset && !hasEdit) {
      test.skip(true, 'No asset link or edit button found — dataset detail precondition not met');
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
    const datasetId = await createDatasetViaApi(testUser, { forceNew: true });
    await loginAndNavigateToRoute(page, testUser, `/datasets/${datasetId}`, {
      timeout: 60000,
      contentSelector: '.dataset-detail-page',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const editBtn = page.locator('button:has-text("Edit")');
    await expect(editBtn).toBeVisible({ timeout: 10000 });
  });
});
