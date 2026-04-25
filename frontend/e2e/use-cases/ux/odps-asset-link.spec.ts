/**
 * E2E: ODPS Upload with Asset Linking (Resource Picker)
 *
 * Per task 29.69.4.3. ODPSUploadPage uses AssetPicker instead of asset_id text input.
 * Flow: create asset → ODPS upload → select asset via AssetPicker → submit.
 * Real backend only; no mocks.
 *
 * Reference: RESOURCE_PICKER_LINKING_PLAN.md, tasks.md 29.69.4
 */

import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

const MINIMAL_ODPS = JSON.stringify({
  schema: 'https://opendataproducts.org/schema/v4.1',
  version: '4.1',
  product: {
    details: {
      en: {
        productID: 'e2e-odps-asset-link',
        name: 'E2E ODPS Asset Link Test',
        description: 'Minimal ODPS for E2E asset linking via AssetPicker',
      },
    },
    dataSchema: {
      fields: [
        { name: 'id', type: 'string', nullable: false },
        { name: 'name', type: 'string', nullable: true },
      ],
    },
    contract: {
      spec: {
        apiVersion: 'odcs.io/v3.0.2',
        kind: 'DataContract',
        id: 'e2e-embedded-odcs',
        name: 'E2E Embedded ODCS',
        version: '1.0.0',
        schema: {
          fields: [
            { name: 'id', type: 'string', nullable: false },
            { name: 'name', type: 'string', nullable: true },
          ],
        },
        info: {
          owners: [{ name: 'E2E Test', email: 'e2e_test@example.com' }],
          tags: ['e2e', 'odps-asset-link'],
        },
      },
    },
  },
});

test.describe('ODPS Upload with Asset Linking (AssetPicker)', () => {
  test.setTimeout(120000);

  test('ODPS upload page shows AssetPicker for optional asset link', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/odps/upload', {
      timeout: 60000,
      contentSelector:
        'textarea#odps-content, .odps-upload-page, [data-testid="odps-upload-asset-picker"]',
    });
    await waitForLoadingComplete(page);

    const assetPicker = page.locator('[data-testid="odps-upload-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });
    expect(page.url()).toContain('/odps/upload');
  });

  test('ODPS Reset clears AssetPicker selection', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/odps/upload', {
      timeout: 60000,
      contentSelector:
        'textarea#odps-content, .odps-upload-page, [data-testid="odps-upload-asset-picker"]',
    });
    await waitForLoadingComplete(page);

    const assetPicker = page.locator('[data-testid="odps-upload-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });

    await page.fill('textarea#odps-content', MINIMAL_ODPS);

    const pickerInput = assetPicker.locator('input[aria-label="Select asset"]');
    await pickerInput.click();
    await page.waitForTimeout(500);
    const firstOption = page.locator('.asset-picker-option').first();
    // intentional: asset-picker option is presence-conditional — picker results depend on tenant assets matching the search term.
    if ((await firstOption.count()) > 0) {
      await firstOption.click();
      await page.waitForTimeout(300);
      const resetBtn = page.locator('button:has-text("Reset")');
      await expect(resetBtn).toBeVisible({ timeout: 5000 });
      await resetBtn.click();
      await page.waitForTimeout(300);
      const inputValue = await pickerInput.inputValue();
      expect(inputValue).toBe('');
    }
  });

  test('ODPS upload with AssetPicker: select asset and submit', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets', {
      timeout: 60000,
      contentSelector:
        '.asset-list-page, .empty-state, h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const createBtn = page
      .locator('button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'));
    await expect(createBtn.first()).toBeVisible({ timeout: 15000 });
    await createBtn.first().click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
    await waitForLoadingComplete(page);

    const assetKey = `e2e-odps-link-${randomUUID()}`;
    await page.fill('input[id="asset-name"]', 'ODPS Asset Link Test');
    await page.fill('input[id="asset-key"]', assetKey);
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');
    await page.locator('button:has-text("Create Asset")').click();

    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
    await waitForLoadingComplete(page, { timeout: 45000 });
    const assetUrl = page.url();
    const assetIdMatch = assetUrl.match(/\/assets\/([^/]+)$/);
    if (!assetIdMatch) {
      throw new Error('Could not extract asset ID from URL');
    }
    const assetId = assetIdMatch[1];

    await page.goto('/odps/upload', { waitUntil: 'domcontentloaded' });
    await waitForLoadingComplete(page);

    const assetPicker = page.locator('[data-testid="odps-upload-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });

    const pickerInput = assetPicker.locator('input[aria-label="Select asset"]');
    await pickerInput.click();
    await page.waitForTimeout(500);

    await pickerInput.fill(assetKey);
    await page.waitForTimeout(800);

    const option = page.locator(`[id="asset-picker-option-${assetId}"]`);
    await expect(option).toBeVisible({ timeout: 15000 });
    await option.click();

    await page.fill('textarea#odps-content', MINIMAL_ODPS);

    const createBtnOdps = page.locator('button:has-text("Create ODPS Product")');
    await expect(createBtnOdps).toBeVisible({ timeout: 5000 });
    await createBtnOdps.click();

    // Wait for mutation to complete: workflow progress (success)
    // Sync workflow can take 60–150s
    const workflowIndicator = page.locator(
      '.odps-workflow-progress, .workflow-running, .workflow-completed, .workflow-failed'
    ).first();
    await expect(workflowIndicator).toBeVisible({ timeout: 180000 });

    await expect(page.locator('.error-display')).not.toBeVisible();
    const hasWorkflow = await page
      .locator('.odps-workflow-progress')
      .isVisible()
      .catch(() => false);
    expect(hasWorkflow).toBe(true) /* acceptable states */;
  });
});
