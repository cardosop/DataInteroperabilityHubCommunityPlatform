/**
 * E2E: DQ Run, Compliance Run, Access Request — Resource Pickers
 *
 * Per task 29.69.5.2. DQRunListPage, ComplianceRunListPage, AccessRequestCreatePage
 * use AssetPicker, DatasetPicker, FilePicker instead of UUID text inputs.
 * Real backend only; no mocks.
 *
 * Reference: tasks.md 29.69.5, RESOURCE_PICKER_LINKING_PLAN.md
 */

import { expect, test } from '@playwright/test';
import { getTestUser, getTenantAdminUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('DQ, Compliance, Access Request: Resource Pickers', () => {
  test.setTimeout(90000);

  test('DQ run create modal shows AssetPicker, DatasetPicker, FilePicker', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq', {
      timeout: 60000,
      contentSelector:
        '.dq-run-list-page, .empty-state, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const createBtn = page
      .locator('button:has-text("Create DQ run")')
      .or(page.locator('.dq-create-run-btn'));
    await expect(createBtn.first()).toBeVisible({ timeout: 15000 });
    await createBtn.first().click();

    const modal = page.locator('.dq-create-modal-overlay');
    await expect(modal).toBeVisible({ timeout: 10000 });

    const assetPicker = page.locator('[data-testid="dq-create-asset-picker"]');
    const datasetPicker = page.locator(
      '[data-testid="dq-create-dataset-picker"]'
    );
    const filePicker = page.locator('[data-testid="dq-create-file-picker"]');

    await expect(assetPicker).toBeVisible({ timeout: 5000 });
    await expect(datasetPicker).toBeVisible({ timeout: 5000 });
    await expect(filePicker).toBeVisible({ timeout: 5000 });
  });

  test('DQ run create: AssetPicker opens and shows options or empty state', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq', {
      timeout: 60000,
      contentSelector:
        '.dq-run-list-page, .empty-state, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const createBtn = page
      .locator('button:has-text("Create DQ run")')
      .or(page.locator('.dq-create-run-btn'));
    if ((await createBtn.count()) === 0) {
      test.skip(true, 'Create DQ run button not rendered — DQ feature may not be enabled');
      return;
    }
    await createBtn.first().click();

    const assetPicker = page.locator('[data-testid="dq-create-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });

    const pickerInput = assetPicker.locator('input[aria-label="Select asset"]');
    await pickerInput.click();
    await page.waitForTimeout(600);

    const hasOptions =
      (await page.locator('.asset-picker-option').count()) > 0;
    const hasEmpty =
      (await page.locator('.asset-picker-empty').count()) > 0;
    const hasLoading =
      (await page.locator('.asset-picker-loading').count()) > 0;

    expect(hasOptions || hasEmpty || hasLoading).toBe(true) /* acceptable states */;
  });

  test('Compliance run create modal shows AssetPicker, DatasetPicker, FilePicker', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/compliance', {
      timeout: 60000,
      contentSelector:
        '.compliance-run-list-page, .empty-state, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const createBtn = page
      .locator('button:has-text("Create compliance run")')
      .or(page.locator('.compliance-create-run-btn'));
    await expect(createBtn.first()).toBeVisible({ timeout: 15000 });
    await createBtn.first().click();

    const modal = page.locator('.compliance-create-modal-overlay');
    await expect(modal).toBeVisible({ timeout: 10000 });

    const assetPicker = page.locator(
      '[data-testid="compliance-create-asset-picker"]'
    );
    const datasetPicker = page.locator(
      '[data-testid="compliance-create-dataset-picker"]'
    );
    const filePicker = page.locator(
      '[data-testid="compliance-create-file-picker"]'
    );

    await expect(assetPicker).toBeVisible({ timeout: 5000 });
    await expect(datasetPicker).toBeVisible({ timeout: 5000 });
    await expect(filePicker).toBeVisible({ timeout: 5000 });
  });

  test('Compliance run create: DatasetPicker opens and shows options or empty state', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/compliance', {
      timeout: 60000,
      contentSelector:
        '.compliance-run-list-page, .empty-state, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const createBtn = page
      .locator('button:has-text("Create compliance run")')
      .or(page.locator('.compliance-create-run-btn'));
    if ((await createBtn.count()) === 0) {
      test.skip(true, 'Create compliance run button not rendered — compliance feature may not be enabled');
      return;
    }
    await createBtn.first().click();

    const datasetPicker = page.locator(
      '[data-testid="compliance-create-dataset-picker"]'
    );
    await expect(datasetPicker).toBeVisible({ timeout: 10000 });

    const pickerInput = datasetPicker.locator(
      'input[aria-label="Select dataset"]'
    );
    await pickerInput.click();
    await page.waitForTimeout(600);

    const hasOptions =
      (await page.locator('.resource-picker-option').count()) > 0;
    const hasEmpty =
      (await page.locator('.resource-picker-empty').count()) > 0;
    const hasLoading =
      (await page.locator('.resource-picker-loading').count()) > 0;

    expect(hasOptions || hasEmpty || hasLoading).toBe(true) /* acceptable states */;
  });

  test('Access Request create page shows AssetPicker, DatasetPicker, FilePicker', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/access-requests/create', {
      timeout: 60000,
      contentSelector:
        '.governance-create-page, h1, [data-testid="access-request-asset-picker"]',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const assetPicker = page.locator(
      '[data-testid="access-request-asset-picker"]'
    );
    const datasetPicker = page.locator(
      '[data-testid="access-request-dataset-picker"]'
    );
    const filePicker = page.locator(
      '[data-testid="access-request-file-picker"]'
    );

    await expect(assetPicker).toBeVisible({ timeout: 10000 });
    await expect(datasetPicker).toBeVisible({ timeout: 5000 });
    await expect(filePicker).toBeVisible({ timeout: 5000 });
  });

  test('Access Request create: FilePicker opens and shows options or empty state', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/access-requests/create', {
      timeout: 60000,
      contentSelector:
        '.governance-create-page, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const filePicker = page.locator(
      '[data-testid="access-request-file-picker"]'
    );
    await expect(filePicker).toBeVisible({ timeout: 10000 });

    const pickerInput = filePicker.locator('input[aria-label="Select file"]');
    await pickerInput.click();
    await page.waitForTimeout(600);

    const hasOptions =
      (await page.locator('.resource-picker-option').count()) > 0;
    const hasEmpty =
      (await page.locator('.resource-picker-empty').count()) > 0;
    const hasLoading =
      (await page.locator('.resource-picker-loading').count()) > 0;

    expect(hasOptions || hasEmpty || hasLoading).toBe(true) /* acceptable states */;
  });
});
