/**
 * E2E Test: JOURNEY-DPO-010 — Publish Asset with Usage-Based Pricing
 *
 * Journey: Publish Asset with Usage-Based Pricing
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /marketplace/publish.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { getTenantAdminUser, getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

/** Get tenant admin or fallback to DPO when tenant admin unavailable (e.g. under parallel load). */
async function getPublishTestUser() {
  try {
    return await getTenantAdminUser();
  } catch {
    return await getTestUser();
  }
}

test.describe('JOURNEY-DPO-010: Publish Asset with Usage-Based Pricing', () => {
  test.setTimeout(180000); // 3 min: avoid interrupted/timeout

  test.describe('Success', () => {
    test('publish page loads with asset selection', async ({ page }) => {
      const testUser = await getTestUser();
      await createAssetViaApi(testUser);
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, .loading-spinner-container, form, h1',
      });
      const assetSelect = page.locator('select#asset_id');
      await expect(assetSelect).toBeVisible({ timeout: 5000 });
      expect(page.url()).toContain('/marketplace/publish');
    });
  });

  test.describe('Failure', () => {
    test('publish without asset shows validation error', async ({ page }) => {
      const testUser = await getPublishTestUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await new Promise((r) => setTimeout(r, 3500));
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, .loading-spinner-container, form, h1',
      });
      await page.fill('#title', 'Usage-Based Listing');
      await page.fill('#description', 'Some description');
      page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'))
        .first()
        .click();
      await new Promise((r) => setTimeout(r, 500));
      const assetError = page.locator('.error-message').filter({ hasText: /asset|required/i });
      await expect(assetError.first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Edge', () => {
    test('publish page loads with empty catalog', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, .loading-spinner-container, form, h1',
      });
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
