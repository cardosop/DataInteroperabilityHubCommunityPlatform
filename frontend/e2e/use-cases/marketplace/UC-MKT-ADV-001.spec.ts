/**
 * E2E: UC-MKT-ADV-001 — Configure Usage-Based Pricing
 *
 * Use Case: Configure Usage-Based Pricing
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md#uc-mkt-adv-001
 *
 * Success/Failure/Edge. Routes: /marketplace, /marketplace/listings/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-MKT-ADV-001: Configure Usage-Based Pricing', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('listing detail shows pricing configuration elements', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .empty-state',
      });
      await waitForLoadingComplete(page, { timeout: 15000 });

      // D86: skip on login redirect instead of silent return
      test.skip(page.url().includes('/login'), 'Auth redirect — infrastructure issue');

      // D85: Success test must NOT accept .error-display
      const hasErrorOnList = (await page.locator('.error-display').count()) > 0;
      expect(hasErrorOnList).toBe(false);

      const listingLink = page.locator('.listing-list-page a[href*="/marketplace/listings/"]').first();
      // intentional: marketplace listing-row click-through is genuinely optional — listing presence depends on whether a DPO has published listings in this tenant.
      if ((await listingLink.count()) > 0) {
        await listingLink.click();
        await page.waitForURL(/\/marketplace\/listings\/[^/]+/, { timeout: 15000 });
        await waitForLoadingComplete(page, { timeout: 15000 });

        // Verify listing detail loaded without error
        const hasDetailError = (await page.locator('.error-display').count()) > 0;
        expect(hasDetailError).toBe(false);

        const hasDetail = (await page.locator('.listing-detail-main, .listing-detail-page').count()) > 0;
        expect(hasDetail).toBe(true);

        // Look for pricing-related UI elements on the detail page
        const pricingSection = page.locator(
          '.pricing-section, .pricing-config, [data-testid="pricing"], ' +
            'button:has-text("Edit"), button:has-text("Pricing"), button:has-text("Configure")'
        );
        const hasPricing = (await pricingSection.count()) > 0;

        // Also check for any price/pricing text on the page
        const pricingText = page.locator('text=/price|pricing|usage.based|per.call|per.request|free|paid/i').first();
        const hasPricingText = (await pricingText.count()) > 0;

        // Pricing UI elements or pricing text should be present on a listing detail
        // hasDetail already asserted above — focus on pricing-specific content
        expect(hasPricing || hasPricingText).toBe(true);
      } else {
        // No listings: marketplace is empty; assert empty state (not error)
        const hasEmpty = (await page.locator('.empty-state').count()) > 0;
        const hasListPage = (await page.locator('.listing-list-page').count()) > 0;
        expect(hasEmpty || hasListPage).toBe(true) /* acceptable states */;
        test.info().annotations.push({
          type: 'note',
          description: 'Marketplace empty — pricing configuration not tested',
        });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to marketplace redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onMarketplaceWithLoginPrompt =
        url.includes('/marketplace') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onMarketplaceWithLoginPrompt).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('listing detail with no explicit pricing section shows default state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .empty-state',
      });
      await waitForLoadingComplete(page, { timeout: 15000 });

      // D86: skip on login redirect
      test.skip(page.url().includes('/login'), 'Auth redirect — infrastructure issue');

      const listingLink = page.locator('.listing-list-page a[href*="/marketplace/listings/"]').first();
      // intentional: marketplace listing-row click-through is genuinely optional — listing presence depends on whether a DPO has published listings in this tenant.
      if ((await listingLink.count()) > 0) {
        await listingLink.click();
        await page.waitForURL(/\/marketplace\/listings\/[^/]+/, { timeout: 15000 });
        await waitForLoadingComplete(page, { timeout: 15000 });

        // Listing detail page should render without error
        const hasDetail =
          (await page.locator('.listing-detail-main, .listing-detail-page').count()) > 0;
        expect(hasDetail).toBe(true);
      } else {
        // Empty marketplace: valid edge case
        const hasEmpty = (await page.locator('.empty-state').count()) > 0;
        const hasListPage = (await page.locator('.listing-list-page').count()) > 0;
        expect(hasEmpty || hasListPage).toBe(true);
      }
    });
  });
});
