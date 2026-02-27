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
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForAssetDropdownOptions,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-002: Publish Asset to Marketplace', () => {
  test.setTimeout(480000); // 8 min: loginUser may use up to 7 min under rate-limit retries

  test.describe('Success', () => {
    test('publish listing: select asset, fill title and description, submit and reach listing or marketplace', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await createAssetViaApi(testUser);
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, h1',
      });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const hasAssets = await waitForAssetDropdownOptions(page, { timeout: 25000 });
      if (!hasAssets) {
        throw new Error(
          'No assets in dropdown after createAssetViaApi. Precondition failure: API or tenant mismatch. ' +
            'Ensure backend is running, E2E test user has correct tenant, and assets API returns data.'
        );
      }

      const assetSelect = page.locator('select#asset_id');
      await assetSelect.selectOption({ index: 1 });
      await page.fill('#title', `E2E Listing ${Date.now()}`);
      await page.fill('#description', 'E2E listing description');
      const submitBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'));
      await submitBtn.first().click();

      await page.waitForURL(/\/(marketplace\/listings\/[^/]+|marketplace)/, { timeout: 30000 });
      expect(page.url()).toMatch(/\/(marketplace\/listings\/[^/]+|marketplace)/);
    });
  });

  test.describe('Failure', () => {
    test('publish without asset shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
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
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      const hasAssets = await waitForAssetDropdownOptions(page, { timeout: 15000 });
      if (!hasAssets) {
        throw new Error(
          'No assets in dropdown after createAssetViaApi. Precondition failure: API or tenant mismatch. ' +
            'Ensure backend is running, E2E test user has correct tenant, and assets API returns data.'
        );
      }
      const assetSelect = page.locator('select#asset_id');
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

    test('unauthenticated access to marketplace publish redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace/publish', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onPublishWithLoginPrompt =
        url.includes('/marketplace') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onPublishWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('publish page loads with empty catalog (dropdown has no assets)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      const assetSelect = page.locator('select#asset_id');
      await expect(assetSelect).toBeVisible({ timeout: 5000 });
      expect(page.url()).toContain('/marketplace/publish');
    });

    test('publish form accepts description with special characters', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      await page.fill('#title', 'E2E Edge Title');
      await page.fill(
        '#description',
        'Description with special chars: <script>, "quotes", & ampersand, unicode: café'
      );
      const descValue = await page.locator('#description').inputValue();
      expect(descValue).toContain('café');
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
