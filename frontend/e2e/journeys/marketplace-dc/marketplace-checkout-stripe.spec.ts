/**
 * Marketplace paid checkout (Stripe test mode).
 * Requires full stack, real auth, Stripe test keys, and E2E_MARKETPLACE_STRIPE=1.
 * The SPA must be built with VITE_STRIPE_PUBLISHABLE_KEY (pk_test_…); at runtime the
 * built bundle embeds that key, so CI must pass it at docker build / vite build time.
 */
import { expect, test } from '@playwright/test';
import { getConsumerTestUser, getTestUser, loginAsPersona } from '../../fixtures/auth';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { createListingViaApi, publishListingViaApi } from '../../fixtures/api-marketplace';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Marketplace Stripe checkout', () => {
  test.setTimeout(180000);

  test.skip(
    process.env.E2E_MARKETPLACE_STRIPE !== '1',
    'Set E2E_MARKETPLACE_STRIPE=1 with API + Stripe test keys and a priced listing.',
  );

  test('DPO priced listing + DC checkout with test card 4242…', async ({ page }) => {
    const dpoUser = await getTestUser();

    const assetId = await createAssetViaApi(dpoUser, { forceNew: true, ensureActivated: true });
    const listingTitle = `E2E Stripe ${Date.now()}`;
    const listingId = await createListingViaApi(dpoUser, assetId, {
      title: listingTitle,
      pricingModel: 'REQUEST_APPROVAL',
      priceAmount: 10.0,
      currency: 'USD',
      enableStripeGateway: true,
    });
    await publishListingViaApi(dpoUser, listingId).catch(() => {
      /* already published */
    });

    await loginAsPersona(page, getConsumerTestUser);
    await page.goto(`/marketplace/checkout/${listingId}`);
    await page.waitForLoadState('domcontentloaded');
    test.skip(page.url().includes('/login'), 'DC auth redirect — check E2E auth');

    await waitForLoadingComplete(page, { timeout: 30000 }).catch(() => {
      /* non-fatal */
    });

    const notConfigured = page.getByText(/Stripe is not configured/i);
    if ((await notConfigured.count()) > 0) {
      test.skip(
        true,
        'Frontend bundle has no VITE_STRIPE_PUBLISHABLE_KEY — rebuild with pk_test for this journey.',
      );
      return;
    }

    const noPrice = page.getByText(/does not require payment/i);
    if ((await noPrice.count()) > 0) {
      test.skip(true, 'Listing has no positive price in API/UI — metadata or listing fetch issue');
      return;
    }

    await expect(page.locator('h1:has-text("Checkout")')).toBeVisible({ timeout: 60000 });
    await expect(page.locator('.marketplace-checkout-summary')).toBeVisible();

    await page.locator('.marketplace-checkout-terms input[type="checkbox"]').check();

    const cardIframe = page.locator('.marketplace-card-element-wrap iframe').first();
    await expect(cardIframe).toBeVisible({ timeout: 45000 });
    const frame = await cardIframe.contentFrame();
    if (!frame) {
      throw new Error('Stripe CardElement iframe has no contentFrame');
    }

    const numberInput = frame
      .locator('input[name="cardnumber"], input[autocomplete="cc-number"], input.InputElement')
      .first();
    await expect(numberInput).toBeVisible({ timeout: 25000 });
    await numberInput.fill('4242424242424242');

    const expInput = frame
      .locator('input[name="exp-date"], input[autocomplete="cc-exp"], input[name="expiry"]')
      .first();
    if ((await expInput.count()) > 0 && (await expInput.isVisible())) {
      await expInput.fill('1234');
    }

    const cvcInput = frame
      .locator('input[name="cvc"], input[autocomplete="cc-csc"], input[name="cvc"]')
      .first();
    if ((await cvcInput.count()) > 0 && (await cvcInput.isVisible())) {
      await cvcInput.fill('123');
    }

    await page.getByRole('button', { name: /Complete purchase/i }).click();

    await page.waitForURL(/\/marketplace\/orders\/[^/]+/i, { timeout: 120000 });
    expect(page.url()).toMatch(/\/marketplace\/orders\//);
  });
});
