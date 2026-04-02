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
import { getTenantAdminUser, getTestUser } from '../../fixtures/auth';
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
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('publish page loads with asset selection', async ({ page }) => {
      const testUser = await getTestUser();
      await createAssetViaApi(testUser);
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, form, h1',
      });
      const assetSelect = page.locator('select#asset_id');
      await expect(assetSelect).toBeVisible({ timeout: 5000 });
      expect(page.url()).toContain('/marketplace/publish');
    });

    test('usage-based pricing fields are present and accept valid input', async ({ page }) => {
      // This test validates that the publish form includes pricing fields:
      // pricing_model select, price_amount numeric input, and currency selector.
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

      // Verify pricing_model select exists (FREE, FREE_AUTO_APPROVE, REQUEST_APPROVAL)
      const pricingModelSelect = page.locator('select#pricing_model, select[name="pricing_model"]').first();
      await expect(pricingModelSelect).toBeVisible({ timeout: 5000 });

      // Verify price_amount input exists and accepts numeric input
      const priceAmountInput = page.locator('input#price_amount, input[name="price_amount"]').first();
      await expect(priceAmountInput).toBeVisible({ timeout: 5000 });
      await priceAmountInput.fill('0.01');
      expect(await priceAmountInput.inputValue()).toBe('0.01');

      // Verify currency selector exists and has USD selected by default
      const currencySelect = page.locator('select#currency, select[name="currency"]').first();
      await expect(currencySelect).toBeVisible({ timeout: 5000 });
      expect(await currencySelect.inputValue()).toBe('USD');

      // Select EUR to verify the selector is functional
      await currencySelect.selectOption('EUR');
      expect(await currencySelect.inputValue()).toBe('EUR');

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
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, form, h1',
      });
      await page.fill('#title', 'Usage-Based Listing');
      await page.fill('#description', 'Some description');
      await page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'))
        .first()
        .click();
      await page.waitForTimeout(500);
      const assetError = page.locator('.error-message').filter({ hasText: /asset|required/i });
      await expect(assetError.first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Edge', () => {
    test('publish page loads with empty catalog', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .listing-publish-form, form, h1',
      });
      expect(page.url()).toContain('/marketplace/publish');
      const hasPublishContent =
        (await page.locator('.listing-publish-page, .listing-publish-form, form').count()) > 0;
      expect(hasPublishContent).toBe(true);
    });
  });
});
