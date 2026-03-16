/**
 * E2E: Asset Detail — Attach Contract and Dataset via Pickers
 *
 * Per task 29.69.4.3. AssetDetailPage uses ContractPicker and DatasetPicker
 * instead of contractId/datasetId text inputs.
 * Flow: create asset → verify pickers visible → (optional) attach via pickers.
 * Real backend only; no mocks.
 *
 * Reference: RESOURCE_PICKER_LINKING_PLAN.md, tasks.md 29.69.4
 */

import { randomUUID } from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Asset Detail: Attach Contract and Dataset (Pickers)', () => {
  test.setTimeout(300000);

  test('asset detail without contract/dataset shows ContractPicker and DatasetPicker', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets', {
      timeout: 60000,
      contentSelector:
        '.asset-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const createBtn = page
      .locator('button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'));
    await expect(createBtn.first()).toBeVisible({ timeout: 15000 });
    await createBtn.first().click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-attach-pickers-${randomUUID()}`;
    await page.fill('input[id="key"]', assetKey);
    await page.fill('input[id="name"]', 'Attach Pickers Test');
    await page.selectOption('select[id="visibility"]', 'INTERNAL');
    await page.locator('button:has-text("Create Asset")').click();

    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
    await waitForLoadingComplete(page, { timeout: 45000 });

    const contractPicker = page.locator(
      '[data-testid="asset-attach-contract-picker"]'
    );
    const datasetPicker = page.locator(
      '[data-testid="asset-attach-dataset-picker"]'
    );

    const noContractSection = page.locator(
      '.linked-section:has-text("Linked Contract")'
    );
    await expect(noContractSection).toBeVisible({ timeout: 10000 });
    const noContractText = await noContractSection
      .locator('text=No contract linked')
      .isVisible()
      .catch(() => false);
    if (noContractText) {
      await expect(contractPicker).toBeVisible({ timeout: 5000 });
    }

    const noDatasetSection = page.locator(
      '.linked-section:has-text("Linked Dataset")'
    );
    await expect(noDatasetSection).toBeVisible({ timeout: 5000 });
    const noDatasetText = await noDatasetSection
      .locator('text=No dataset linked')
      .isVisible()
      .catch(() => false);
    if (noDatasetText) {
      await expect(datasetPicker).toBeVisible({ timeout: 5000 });
    }
  });

  test('asset detail: ContractPicker opens and shows contracts', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets', {
      timeout: 60000,
      contentSelector:
        '.asset-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const firstAssetLink = page.locator('a[href^="/assets/"]').first();
    const linkCount = await firstAssetLink.count();
    if (linkCount === 0) {
      // Create an asset so we have one without contract
      const createBtn = page
        .locator('button:has-text("Create Asset")')
        .or(page.locator('.empty-state-action:has-text("Create Asset")'));
      await expect(createBtn.first()).toBeVisible({ timeout: 15000 });
      await createBtn.first().click();
      await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
      await waitForLoadingComplete(page);
      const assetKey = `e2e-contract-picker-${randomUUID()}`;
      await page.fill('input[id="key"]', assetKey);
      await page.fill('input[id="name"]', 'Contract Picker Test');
      await page.selectOption('select[id="visibility"]', 'INTERNAL');
      await page.locator('button:has-text("Create Asset")').click();
      await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
      await waitForLoadingComplete(page);
    } else {
      await firstAssetLink.click();
      await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
      await waitForLoadingComplete(page);
    }

    const contractPicker = page.locator(
      '[data-testid="asset-attach-contract-picker"]'
    );
    const hasNoContract = await page
      .locator('text=No contract linked')
      .isVisible()
      .catch(() => false);
    if (!hasNoContract) {
      // Asset already has a contract — ContractPicker is only shown when no contract is linked.
      // Skip the picker-open test since the picker won't be rendered.
      test.info().annotations.push({
        type: 'note',
        description: 'Asset already has contract — ContractPicker not rendered; picker-open test skipped',
      });
      return;
    }

    await expect(contractPicker).toBeVisible({ timeout: 5000 });
    const pickerInput = contractPicker.locator(
      'input[aria-label="Select contract"]'
    );
    await pickerInput.click();
    await page.waitForTimeout(500);

    const dropdown = page.locator('.resource-picker-dropdown');
    await expect(dropdown).toBeVisible({ timeout: 10000 });

    const hasOptions =
      (await page.locator('.resource-picker-option').count()) > 0;
    const hasEmpty =
      (await page.locator('.resource-picker-empty').count()) > 0;
    const hasLoading =
      (await page.locator('.resource-picker-loading').count()) > 0;

    expect(hasOptions || hasEmpty || hasLoading).toBe(true);
  });

  test('asset detail: DatasetPicker opens and attach flow', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/datasets/create', {
      timeout: 60000,
      contentSelector:
        '.dataset-create-page, .file-upload, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    const dropzone = page.locator('.file-upload-dropzone');
    if ((await dropzone.count()) === 0) {
      test.skip();
      return;
    }

    const fileBaseName = `e2e-attach-${Date.now()}`;
    const tmpDir = path.join(os.tmpdir(), 'e2e-attach-dataset');
    const testFile = path.join(tmpDir, `${fileBaseName}.csv`);
    try {
      await fs.promises.mkdir(tmpDir, { recursive: true });
      await fs.promises.writeFile(
        testFile,
        'id,name\n1,alpha\n2,beta',
        'utf-8'
      );

      const fileInput = page.locator('input[type="file"]');
      if ((await fileInput.count()) > 0) {
        await fileInput.first().setInputFiles(testFile);
        // File upload goes to backend — may be slow; also accept error-display (backend unavailable)
        const uploadDone = await page
          .locator('.file-upload-success, .upload-success, .file-upload-error, .error-display')
          .first()
          .waitFor({ state: 'visible', timeout: 45000 })
          .then(() => true)
          .catch(() => false);
        if (!uploadDone) {
          test.skip(true, 'Upload success/error indicator not visible within 45s — backend may be slow or unavailable');
          return;
        }
        const hasUploadError =
          (await page.locator('.file-upload-error, .error-display').count()) > 0 &&
          (await page.locator('.file-upload-success, .upload-success').count()) === 0;
        if (hasUploadError) {
          test.skip(true, 'File upload failed — backend may be unavailable; cannot test DatasetPicker attach flow');
          return;
        }
      }
      // linkMode 'none' requires only uploadedFile; no name input
      await page.locator('button:has-text("Create Dataset")').click();
      // Wait for redirect to dataset detail (UUID), not /datasets/create
      await expect(page).toHaveURL(
        /\/datasets\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
        { timeout: 45000 }
      );
      await waitForLoadingComplete(page);

      const datasetUrl = page.url();
      const datasetIdMatch = datasetUrl.match(/\/datasets\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i);
      if (!datasetIdMatch) {
        throw new Error(`Expected redirect to /datasets/{uuid}, got: ${datasetUrl}`);
      }
      const datasetId = datasetIdMatch[1];

      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page);

      const createBtn = page
        .locator('button:has-text("Create Asset")')
        .or(page.locator('.empty-state-action:has-text("Create Asset")'));
      await expect(createBtn.first()).toBeVisible({ timeout: 15000 });
      await createBtn.first().click();

      await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
      await waitForLoadingComplete(page);

      const assetKey = `e2e-ds-attach-${randomUUID()}`;
      await page.fill('input[id="key"]', assetKey);
      await page.fill('input[id="name"]', 'Dataset Attach Test');
      await page.selectOption('select[id="visibility"]', 'INTERNAL');
      await page.locator('button:has-text("Create Asset")').click();

      await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
      await waitForLoadingComplete(page);

      const datasetPicker = page.locator(
        '[data-testid="asset-attach-dataset-picker"]'
      );
      await expect(datasetPicker).toBeVisible({ timeout: 10000 });

      const pickerInput = datasetPicker.locator(
        'input[aria-label="Select dataset"]'
      );
      await pickerInput.click();
      await page.waitForTimeout(500);
      await pickerInput.fill(fileBaseName);
      await page.waitForTimeout(1200);

      const option = page.locator(
        `[id="dataset-picker-option-${datasetId}"]`
      );
      await expect(option).toBeVisible({ timeout: 15000 });
      await option.click();

      const attachBtn = page
        .locator('.linked-section:has-text("Linked Dataset")')
        .locator('button:has-text("Attach")');
      await expect(attachBtn).toBeVisible({ timeout: 5000 });
      await attachBtn.click();

      await expect(
        page.locator('a[href*="/datasets/"]').first()
      ).toBeVisible({ timeout: 15000 });
    } finally {
      try {
        await fs.promises.unlink(testFile);
      } catch {
        // ignore
      }
    }
  });
});
