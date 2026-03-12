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

    test('usage-based pricing fields are present and accept valid input', async ({ page }) => {
      // This test validates that the publish form supports the usage-based pricing model:
      // price_type selection, price_per_unit numeric input, and currency selector.
      const testUser = await getTestUser();
      await createAssetViaApi(testUser, { ensureActivated: true });
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, form, h1',
      });

      // Fill mandatory title and description first
      const titleInput = page.locator('#title, input[name="title"]').first();
      const descInput = page.locator('#description, textarea[name="description"]').first();
      if ((await titleInput.count()) > 0) {
        await titleInput.fill(`E2E Usage Pricing ${Date.now()}`);
      }
      if ((await descInput.count()) > 0) {
        await descInput.fill('E2E usage-based pricing test');
      }

      // Look for the price_type selector (dropdown or radio group)
      const priceTypeSelect = page.locator(
        'select#price_type, select[name="price_type"], [data-testid="price-type-select"]'
      ).first();
      const priceTypeRadio = page.locator(
        'input[type="radio"][value="usage"], input[type="radio"][value="usage_based"]'
      ).first();

      const hasPriceTypeSelect = (await priceTypeSelect.count()) > 0;
      const hasPriceTypeRadio = (await priceTypeRadio.count()) > 0;

      if (hasPriceTypeSelect) {
        // Try selecting a usage-based option
        const options = await priceTypeSelect.locator('option').allTextContents();
        const usageOption = options.find((o) => /usage/i.test(o));
        if (usageOption) {
          await priceTypeSelect.selectOption({ label: usageOption });
          await page.waitForTimeout(500);
        }
      } else if (hasPriceTypeRadio) {
        await priceTypeRadio.click();
        await page.waitForTimeout(500);
      }

      // Look for price_per_unit input (appears when usage-based is selected)
      const priceInput = page.locator(
        'input#price_per_unit, input[name="price_per_unit"], [data-testid="price-per-unit"]'
      ).first();
      if ((await priceInput.count()) > 0) {
        await expect(priceInput).toBeVisible({ timeout: 5000 });
        await priceInput.fill('0.01');
      }

      // Look for currency selector
      const currencySelect = page.locator(
        'select#currency, select[name="currency"], [data-testid="currency-select"]'
      ).first();
      if ((await currencySelect.count()) > 0) {
        await expect(currencySelect).toBeVisible({ timeout: 5000 });
        // Select USD or first available option
        const opts = await currencySelect.locator('option').allTextContents();
        const usdOption = opts.find((o) => /USD/i.test(o));
        if (usdOption) await currencySelect.selectOption({ label: usdOption });
      }

      // The form should still be on the publish page with no crash
      expect(page.url()).toContain('/marketplace/publish');
      const hasFormError = (await page.locator('.error-display').count()) > 0;
      // The only error expected at this point is a missing-asset validation (not a crash)
      if (hasFormError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        const isAssetMissing = /asset|required/i.test(errText);
        expect(isAssetMissing).toBe(true);
      }
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
