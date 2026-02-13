/**
 * E2E Test: Asset Creation Flow
 * Independent test for asset creation (extracted from complete journey)
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Asset Creation Flow', () => {
  test.setTimeout(120000); // 2 minutes

  test('should create asset successfully', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    // Navigate to assets page
    await page.goto('/assets');
    await waitForLoadingComplete(page);

    // Wait for create button to be visible
    const createButton = page
      .locator('button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'));
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });
    await createButton.first().click();

    // Wait for create page
    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
    await waitForLoadingComplete(page);

    // Fill form
    const assetKey = `test-asset-${Date.now()}`;
    await expect(page.locator('input[id="key"]')).toBeVisible({ timeout: 10000 });
    await page.fill('input[id="key"]', assetKey);
    await page.fill('input[id="name"]', 'Test Asset');
    await page.fill('textarea[id="description"]', 'Test asset description');
    await page.selectOption('select[id="visibility"]', 'INTERNAL');

    // Submit
    const submitButton = page.locator('button:has-text("Create Asset")');
    await expect(submitButton).toBeVisible({ timeout: 10000 });
    await submitButton.click();

    // Wait for redirect to detail page
    await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 15000 });
    await waitForLoadingComplete(page);

    // Verify asset was created
    const assetHeading = page.locator('.asset-detail-page h1, .asset-detail-content h1').first();
    await expect(assetHeading).toBeVisible({ timeout: 10000 });
    await expect(assetHeading).toContainText('Test Asset', { timeout: 10000 });
    await expect(page.locator('.status-badge').first()).toContainText('DRAFT');
  });
});
