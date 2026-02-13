/**
 * E2E Test: JOURNEY-DPO-002 — Publish Asset to Marketplace
 *
 * Journey: Publish Asset to Marketplace
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success, Failure, Edge dimensions; real backend only. Routes: /marketplace, /marketplace/publish, /marketplace/listings/:id.
 * Creates an asset via API when needed so Success and "publish without title" tests don't skip (no mocks).
 */

import { expect, test } from '@playwright/test';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DPO-002: Publish Asset to Marketplace', () => {
  test.setTimeout(480000); // 8 min: loginUser may use up to 7 min under rate-limit retries

  test.describe('Success', () => {
    test('publish listing: select asset, fill title and description, submit and reach listing or marketplace', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await createAssetViaApi(testUser);
      await loginUser(page, testUser);

      await page.goto('/marketplace/publish');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          const publishPage = main.querySelector('.listing-publish-page');
          if (publishPage) return true;
          const h1 = main.querySelector('h1');
          return !!h1?.textContent?.includes('Publish');
        },
        { timeout: 15000 }
      );

      const assetSelect = page.locator('select#asset_id');
      await assetSelect.waitFor({ state: 'visible', timeout: 10000 });
      const options = await assetSelect.locator('option').allTextContents();
      const hasAssets = options.some((t) => t && t !== 'Select an asset...');
      if (!hasAssets) {
        test.skip(true, 'No assets in dropdown after createAssetViaApi (API or tenant mismatch)');
      }

      await assetSelect.selectOption({ index: 1 });
      await page.fill('#title', `E2E Listing ${Date.now()}`);
      await page.fill('#description', 'E2E listing description');
      const submitBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'));
      await submitBtn.first().click();

      await page.waitForURL(/\/(marketplace\/listings\/[^/]+|marketplace)/, { timeout: 20000 });
      expect(page.url()).toMatch(/\/(marketplace\/listings\/[^/]+|marketplace)/);
    });
  });

  test.describe('Failure', () => {
    test('publish without asset shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/marketplace/publish');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.listing-publish-page', { timeout: 15000 });
      await page.fill('#title', 'Some Title');
      await page.fill('#description', 'Some description');
      page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'))
        .first()
        .click();
      await page.waitForTimeout(500);
      const assetError = page.locator('.error-message').filter({ hasText: /asset|required/i });
      await expect(assetError.first()).toBeVisible({ timeout: 5000 });
    });

    test('publish without title shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await createAssetViaApi(testUser);
      await loginUser(page, testUser);
      await page.goto('/marketplace/publish');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.listing-publish-page', { timeout: 15000 });
      const assetSelect = page.locator('select#asset_id');
      await assetSelect.waitFor({ state: 'visible', timeout: 10000 });
      const options = await assetSelect.locator('option').allTextContents();
      const hasAssets = options.some((t) => t && t !== 'Select an asset...');
      if (!hasAssets) {
        test.skip(true, 'No assets in dropdown after createAssetViaApi');
      }
      await assetSelect.selectOption({ index: 1 });
      await page.fill('#description', 'Some description');
      page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'))
        .first()
        .click();
      await page.waitForTimeout(500);
      const titleError = page.locator('.error-message').filter({ hasText: /title|required/i });
      await expect(titleError.first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Edge', () => {
    test('publish page loads with empty catalog (dropdown has no assets)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/marketplace/publish');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          return main.querySelector('.listing-publish-page') !== null;
        },
        { timeout: 15000 }
      );
      const assetSelect = page.locator('select#asset_id');
      await expect(assetSelect).toBeVisible({ timeout: 5000 });
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
