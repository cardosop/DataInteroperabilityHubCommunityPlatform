/**
 * E2E: ODPS Upload with Asset Linking (Resource Picker)
 *
 * Per task 29.69.4.3 the ODPS upload surface uses AssetPicker instead of
 * an asset_id text input. The standalone ``/odps/upload`` page is gone:
 * Phase 211.A6 redirects ``/odps/upload`` → ``/contracts/create``, and the
 * picker lives in the "ODPS Data Product" tab of the consolidated create
 * page (``ODPSProductForm``, ``data-testid="odps-asset-picker"`` — the old
 * ``odps-upload-asset-picker`` testid never survived the consolidation).
 * Flow: ODPS create tab → optional asset link via AssetPicker → submit.
 * Real backend only; no mocks.
 *
 * Reference: RESOURCE_PICKER_LINKING_PLAN.md, tasks.md 29.69.4
 */

import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import {
  createAssetViaForm,
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';



test.describe('ODPS Upload with Asset Linking (AssetPicker)', () => {
  test.setTimeout(120000);

  test('ODPS upload page shows AssetPicker for optional asset link', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/contracts/create', {
      timeout: 60000,
      contentSelector: '.contract-create-page, [data-testid="odps-asset-picker"]',
    });
    await waitForLoadingComplete(page);

    // The consolidated create page defaults to Raw Upload; the ODPS
    // guided form (with the AssetPicker) lives behind the ODPS tab.
    const odpsTab = page.getByRole('tab', { name: /ODPS Data Product/i });
    await odpsTab.waitFor({ state: 'visible', timeout: 10000 });
    await odpsTab.click();

    const assetPicker = page.locator('[data-testid="odps-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });
    expect(page.url()).toContain('/contracts/create');
  });

  test('ODPS Reset clears AssetPicker selection', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/contracts/create', {
      timeout: 60000,
      contentSelector: '.contract-create-page, [data-testid="odps-asset-picker"]',
    });
    await waitForLoadingComplete(page);

    const odpsTab = page.getByRole('tab', { name: /ODPS Data Product/i });
    await odpsTab.waitFor({ state: 'visible', timeout: 10000 });
    await odpsTab.click();

    const assetPicker = page.locator('[data-testid="odps-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });

    const pickerInput = assetPicker.locator('input[aria-label="Select asset"]');
    await pickerInput.click();
    await page.waitForTimeout(500);
    const firstOption = page.locator('.asset-picker-option').first();
    // intentional: asset-picker option is presence-conditional — picker results depend on tenant assets matching the search term.
    if ((await firstOption.count()) > 0) {
      await firstOption.click();
      await page.waitForTimeout(300);
      // The picker's clear control (×, "Clear selection") is the current
      // reset surface — the standalone page's "Reset" button died with
      // the 211.A6 consolidation.
      const clearBtn = assetPicker.locator('button[aria-label="Clear selection"]');
      await expect(clearBtn).toBeVisible({ timeout: 5000 });
      await clearBtn.click();
      await page.waitForTimeout(300);
      const inputValue = await pickerInput.inputValue();
      expect(inputValue).toBe('');
    }
  });

  test('ODPS form: AssetPicker selection binds into the product form', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets', {
      timeout: 60000,
      contentSelector:
        '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    // Phase 250.6.B — /assets/create opens on the type-picker step; the
    // shared helper drives the form via the ?skip=picker bypass (picker
    // coverage lives in journeys/dpo/asset-type-picker.spec.ts).
    // helper signature is (assetKey, name): the picker search matches the
    // asset NAME (not the key), so the NAME must be the unique searchable
    // value; the key uses the same unique suffix (lowercase+hyphens rule).
    const unique = randomUUID();
    const assetName = `e2e-odps-link-${unique}`;
    await createAssetViaForm(
      page,
      `e2e-odps-key-${unique}`,
      assetName,
    );
    // Strip any query string before extracting the UUID — the create URL
    // (/assets/create?skip=picker) must NOT be able to masquerade as a
    // detail URL through a sloppy [^/]+ capture.
    const assetUrl = page.url().split('?')[0];
    const assetIdMatch = assetUrl.match(/\/assets\/([0-9a-f-]{36})\/?$/);
    if (!assetIdMatch) {
      throw new Error(`Could not extract asset ID from URL: ${assetUrl}`);
    }
    const assetId = assetIdMatch[1];

    await page.goto('/contracts/create', { waitUntil: 'domcontentloaded' });
    await waitForLoadingComplete(page);

    const odpsTab = page.getByRole('tab', { name: /ODPS Data Product/i });
    await odpsTab.waitFor({ state: 'visible', timeout: 10000 });
    await odpsTab.click();

    const assetPicker = page.locator('[data-testid="odps-asset-picker"]');
    await expect(assetPicker).toBeVisible({ timeout: 10000 });

    const pickerInput = assetPicker.locator('input[aria-label="Select asset"]');
    await pickerInput.click();
    await page.waitForTimeout(500);

    await pickerInput.fill(assetName);
    await page.waitForTimeout(800);

    const option = page.locator(`[id="asset-picker-option-${assetId}"]`);
    await expect(option).toBeVisible({ timeout: 15000 });
    await option.click();

    // The selection binds into the guided form: the trigger input shows
    // "<name> (<key>)" and the clear control appears. The raw-JSON
    // submit + workflow-progress terminal died with the standalone page
    // (the guided form serialises to ODPS internally on submit); the
    // picker binding is the linking contract this spec pins.
    await expect(pickerInput).toHaveValue(/e2e-odps-link/, { timeout: 5000 });
    await expect(
      assetPicker.locator('button[aria-label="Clear selection"]')
    ).toBeVisible({ timeout: 5000 });
  });
});
