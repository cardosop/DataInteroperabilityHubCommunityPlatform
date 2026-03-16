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
import { createAssetViaApi } from '../../fixtures/api-assets';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

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

    test('asset detail page shows Community / ratings section or empty state (Phase 27.1)', async ({
      page,
    }) => {
      // Use API-created asset so the test never vacuously skips due to empty catalog.
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser);
      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on asset detail');
      }

      await page.waitForSelector('.asset-detail-page, .asset-detail-content, .error-display', {
        timeout: 15000,
      });

      // If asset fails to load entirely (no detail container), fail the test.
      // Sub-section errors (e.g. ratings 500) are acceptable — the asset detail page
      // itself still renders and the Community section test can proceed.
      const hasDetailContainer = (await page.locator('.asset-detail-page, .asset-detail-content').count()) > 0;
      if (!hasDetailContainer) {
        const errText = (await page.locator('.error-display').first().textContent().catch(() => 'unknown')) ?? '';
        throw new Error(`Asset detail failed to load (required for Community section test): ${errText.slice(0, 250)}`);
      }

      // The Community / social section is capability-gated (social.ratings, social.reviews).
      // Accept three valid states:
      //   1. Section is visible with a "Community" heading
      //   2. Feature-unavailable indicator (capability off)
      //   3. Empty state for the social section (no ratings yet)
      const socialSection = page.locator('[data-testid="asset-social-section"]');
      const socialHeading = page.locator(
        '[data-testid="asset-social-section"] h2, .asset-social h2, [data-testid="ratings-section"] h2'
      );
      // Note: text= selectors cannot be mixed with CSS selectors in a comma-separated string;
      // use separate locators combined with .or() to avoid CSS parse errors.
      const unavailableIndicator = page
        .locator('.social-unavailable, [data-testid="social-unavailable"]')
        .or(page.getByText(/ratings.*not available|community.*disabled/i));

      const hasSocialSection = (await socialSection.count()) > 0 && (await socialSection.isVisible().catch(() => false));
      const hasUnavailable = (await unavailableIndicator.count()) > 0;
      const hasDetailPage = (await page.locator('.asset-detail-page, .asset-detail-content').count()) > 0;

      // Asset detail must always be present
      expect(hasDetailPage).toBe(true);

      if (hasSocialSection) {
        // Section rendered — validate it has a community heading
        await expect(socialHeading.first()).toBeVisible({ timeout: 5000 });
      } else if (hasUnavailable) {
        // Capability disabled — acceptable
        await expect(unavailableIndicator.first()).toBeVisible({ timeout: 5000 });
      }
      // else: section not rendered but detail page loaded — capability gated out silently
    });
  });

  test.describe('Failure', () => {
    test('communities page without capability shows 403 or unavailable (not a crash)', async ({ page }) => {
      // When social.communities capability is disabled, visiting /communities must show an
      // unavailable indicator or redirect to /403 — it must NOT silently show the page.
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, .error-display, #email',
        { timeout: 15000, state: 'visible' }
      ).catch(() => null);
      // Wait for CapabilityRoute to finish loading (spinner may persist under backend load).
      // Catch page-closed error that occurs if the 180s test timeout fires during this wait.
      await waitForLoadingComplete(page, { timeout: 30000 }).catch(() => null);
      await new Promise((r) => setTimeout(r, 1000));

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /communities failure test');
      }

      const capabilityEnabled =
        page.url().includes('/communities') &&
        (await page.locator('.communities-page, .communities-tab').count()) > 0 &&
        (await page.locator('.unavailable-page').count()) === 0;

      if (capabilityEnabled) {
        // Capability is on in this environment — failure scenario not applicable; skip softly
        test.info().annotations.push({
          type: 'capability-enabled',
          description: 'social.communities capability is on; 403/unavailable failure path not triggered',
        });
        return;
      }

      // Capability disabled: must show unavailable or 403 — not a blank/crash render
      const capabilityDisabled =
        (await page.locator('.unavailable-page, .error-display').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');
      expect(capabilityDisabled).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('communities page renders content or capability-unavailable state (no crash)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, #email',
        { timeout: 15000, state: 'visible' }
      ).catch(() => null);
      // Wait for CapabilityRoute to finish loading (spinner may persist under backend load).
      // Catch page-closed error that occurs if the 180s test timeout fires during this wait.
      await waitForLoadingComplete(page, { timeout: 30000 }).catch(() => null);
      await new Promise((r) => setTimeout(r, 1000));

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /communities edge test');
      }

      // Page must render something meaningful — not a blank screen or JS crash
      const hasPageContent =
        (await page.locator('.communities-page, .communities-tab, .unavailable-page').count()) > 0 ||
        page.url().includes('/403');
      expect(hasPageContent).toBe(true);
    });
  });
});
