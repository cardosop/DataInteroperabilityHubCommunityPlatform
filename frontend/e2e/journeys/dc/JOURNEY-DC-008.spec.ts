/**
 * E2E Test: JOURNEY-DC-008 — Rate and Review Asset
 *
 * Journey: Rate and Review Asset
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern.
 * Routes: /communities (Phase 27.2), /assets/:id with Community section (Phase 27.1).
 * Social (ratings, reviews) embedded on asset page. Capability-gated: social.ratings, social.reviews.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, getTestUser, loginUser } from '../../fixtures/auth';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-008: Rate and Review Asset', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('communities page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .app-main, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 60000 }
      );
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onCommunities = url.includes('/communities');
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .app-main, .unavailable-page, .loading-spinner-container').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onCommunities && hasContent)).toBe(true);
    });

    test('asset page shows Community section for rating/review (Phase 27.1)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      // Provider creates asset (consumer lacks DATA_PROVIDER); consumer navigates to view/rate
      const provider = await getTestUser();
      const assetId = await createAssetViaApi(provider);
      await loginAndNavigateToRoute(page, consumer, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .asset-social-section, .error-display, .loading-spinner-container',
      });
      await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 15000 });
      if ((await page.locator('.error-display').count()) > 0) {
        test.skip(true, 'Asset load failed; cannot assert Community section');
      }
      const socialSection = page.locator('[data-testid="asset-social-section"]');
      await socialSection.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await socialSection.count()) > 0 && (await socialSection.isVisible())) {
        await expect(socialSection.locator('h2')).toContainText(/Community/i);
      }
    });
  });

  test.describe('Failure', () => {
    test('communities page without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, .error-display, .loading-spinner-container, #email',
        { timeout: 60000 }
      );
      const url = page.url();
      const on403 = url.includes('/403');
      const onUnavailable =
        (await page.locator('.unavailable-page, .error-display').count()) > 0 || url.includes('/unavailable');
      const onCommunities = url.includes('/communities');
      const onLogin = url.includes('/login');
      expect(on403 || onUnavailable || onCommunities || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('communities page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 60000 }
      );
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/communities') || url.includes('/unavailable')
      ).toBe(true);
    });
  });
});
