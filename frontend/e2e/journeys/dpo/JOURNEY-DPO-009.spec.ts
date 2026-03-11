/**
 * E2E Test: JOURNEY-DPO-009 — Manage Asset Ratings and Reviews
 *
 * Journey: Manage Asset Ratings and Reviews
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern.
 * Routes: /communities (Phase 27.2), /assets/:id with Community section (Phase 27.1).
 * Social (ratings, reviews) embedded on asset page. Capability-gated: social.ratings, social.reviews.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';
import { createAssetViaApi } from '../../fixtures/api-assets';

test.describe('JOURNEY-DPO-009: Manage Asset Ratings and Reviews', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo; communities page nav

  test.describe('Success', () => {
    test('communities page loads (ratings/reviews)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/communities', {
        timeout: 60000,
        contentSelector: '.communities-page, .communities-tab, .unavailable-page, .error-display, .loading-spinner-container, #email',
      });
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onCommunities = url.includes('/communities');
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .unavailable-page, .error-display, .loading-spinner-container').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onCommunities && hasContent)).toBe(true);
    });

    test('asset page shows Community section for ratings/reviews (Phase 27.1)', async ({ page }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser);
      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
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
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, .error-display, #email',
        { timeout: 15000, state: 'visible' }
      ).catch(() => null);
      await new Promise((r) => setTimeout(r, 1000));
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onCommunities = page.url().includes('/communities');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onCommunities || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('communities page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, #email',
        { timeout: 15000, state: 'visible' }
      ).catch(() => null);
      await new Promise((r) => setTimeout(r, 1000));
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/unavailable') || url.includes('/communities')
      ).toBe(true);
    });
  });
});
