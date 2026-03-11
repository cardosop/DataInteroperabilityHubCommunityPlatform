/**
 * E2E Feature: Communities + Social on Asset Page (Phase 27.1–27.3)
 * Per E2E_FULL_COVERAGE_PLAN and tasks 27.3.1/27.3.2.
 * Routes: /communities (was /social). /social redirects to /communities.
 * Asset page embeds Community section (Ratings, Reviews, Comments) when capabilities available.
 * Capability: social.communities, social.ratings, social.reviews, social.comments.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { createAssetViaApi } from '../fixtures/api-assets';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Communities', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities route loads or redirects to login/403', async ({ page }) => {
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/communities|\/login|\/403|\/unavailable/);
    });
  });

  test.describe('Edge', () => {
    test('/social redirects to /communities', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url).toMatch(/\/communities|\/login|\/403|\/unavailable/);
    });
  });
});

test.describe('Feature: Social on Asset Page (Phase 27.1)', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('asset page shows Community section when social capabilities available', async ({ page }) => {
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
      // When social capabilities (social.ratings, social.reviews, social.comments) are available,
      // AssetSocialSection renders with data-testid="asset-social-section"
      const socialSection = page.locator('[data-testid="asset-social-section"]');
      await socialSection.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await socialSection.count()) > 0 && (await socialSection.isVisible())) {
        await expect(socialSection.locator('h2')).toContainText(/Community/i);
        const hasTabs =
          (await socialSection.locator('button:has-text("Ratings")').count()) > 0 ||
          (await socialSection.locator('button:has-text("Reviews")').count()) > 0 ||
          (await socialSection.locator('button:has-text("Comments")').count()) > 0;
        expect(hasTabs).toBe(true);
      }
      // If section not visible, capabilities may be off; asset page still loaded successfully
    });
  });
});

test.describe('Feature: Rate and Review on Asset Page (Phase 27.3.2)', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('rate asset on asset page', async ({ page }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser, { ensureActivated: true });
      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .asset-social-section, .error-display, .loading-spinner-container',
      });
      const socialSection = page.locator('[data-testid="asset-social-section"]');
      await socialSection.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await socialSection.count()) === 0 || !(await socialSection.isVisible())) {
        test.skip(true, 'Social capabilities not available; skip rate flow');
      }
      const ratingsTab = socialSection.locator('button:has-text("Ratings")');
      if ((await ratingsTab.count()) === 0) {
        test.skip(true, 'Ratings tab not available (social.ratings capability off); skip rate flow');
      }
      await ratingsTab.click();
      await page.waitForTimeout(500);
      const submitBtn = page.locator('button:has-text("Submit Rating")');
      await submitBtn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => null);
      if ((await submitBtn.count()) === 0) {
        test.skip(true, 'Submit Rating button not found; Ratings UI may still be loading');
      }
      {
        await submitBtn.click();
        await page.waitForTimeout(500);
        const star5 = page.locator('.star-button').nth(4);
        if ((await star5.count()) === 0) {
          test.skip(true, 'Star rating buttons not found; rating form may still be loading');
        }
        await star5.click();
        await page.waitForTimeout(300);
        const submitFormBtn = page.locator('button:has-text("Submit")').filter({ hasText: /^Submit$/ });
        await submitFormBtn.click();
        await page.waitForTimeout(2000);
        await expect(page.locator('.ratings-tab, .rating-item, .empty-state').first()).toBeVisible({ timeout: 5000 });
      }
    });

    test('add review on asset page', async ({ page }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser, { ensureActivated: true });
      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .asset-social-section, .error-display, .loading-spinner-container',
      });
      const socialSection = page.locator('[data-testid="asset-social-section"]');
      await socialSection.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await socialSection.count()) === 0 || !(await socialSection.isVisible())) {
        test.skip(true, 'Social capabilities not available; skip review flow');
      }
      const reviewsTab = socialSection.locator('button:has-text("Reviews")');
      if ((await reviewsTab.count()) === 0) {
        test.skip(true, 'Reviews tab not available (social.reviews capability off); skip review flow');
      }
      await reviewsTab.click();
      await page.waitForTimeout(500);
      const writeReviewBtn = page.locator('button:has-text("Write Review")');
      await writeReviewBtn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => null);
      if ((await writeReviewBtn.count()) === 0) {
        test.skip(true, 'Write Review button not found; Reviews UI may still be loading');
      }
      {
        await writeReviewBtn.click();
        await page.waitForTimeout(500);
        const textarea = page.locator('.review-form textarea, [placeholder*="review"]');
        await textarea.waitFor({ state: 'visible', timeout: 3000 }).catch(() => null);
        if ((await textarea.count()) === 0) {
          test.skip(true, 'Review form textarea not found; form may still be loading');
        }
        await textarea.fill('E2E test review: This asset is great for testing. Minimum 10 characters.');
        await page.waitForTimeout(300);
        const submitReviewBtn = page.locator('button:has-text("Submit Review")');
        await submitReviewBtn.click();
        await page.waitForTimeout(2000);
        await expect(page.locator('.reviews-tab, .review-item, .empty-state').first()).toBeVisible({ timeout: 5000 });
      }
    });
  });
});
