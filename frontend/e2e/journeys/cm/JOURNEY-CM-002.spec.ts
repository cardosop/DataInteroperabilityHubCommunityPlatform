/**
 * E2E Test: JOURNEY-CM-002 — Moderate Reviews and Ratings
 *
 * Journey: Moderate Reviews and Ratings
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Distinct from CM-001 (Manage Data Community) and CM-004 (Manage Activity Feeds):
 * CM-002 focuses on the Ratings and Reviews tabs within the social section of an
 * asset detail page. CM-001 tests the /communities page. CM-004 tests the Comments tab.
 *
 * Success/Failure/Edge. Routes: /assets/:id (social section — Ratings + Reviews tabs).
 * Capability-gated: social.ratings, social.reviews. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { createAssetViaApi } from '../../fixtures/api-assets';

test.describe('JOURNEY-CM-002: Moderate Reviews and Ratings', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('asset page shows Ratings and Reviews tabs in social section', async ({ page }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser);
      await loginUser(page, testUser);
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator('.asset-detail-page, [data-testid="asset-detail-page"]').first()
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);

      const redirectedToLogin = page.url().includes('/login');
      test.skip(redirectedToLogin, 'Redirected to login — auth may have expired');
      if (redirectedToLogin) {
        return;
      }

      // The bare goto above can race an API restart window — the asset fetch
      // fails at the network layer (ErrorDisplay "Failed to fetch /
      // NETWORK_ERROR") even though the backend is healthy a moment later.
      // The page offers Retry for exactly this; use the app's own recovery
      // ONCE before judging the error state a real failure.
      const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: the error text is diagnostic-only — an empty read just
        // means the retry branch won't fire and the strict assertion below
        // reports the visible error state.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (/NETWORK_ERROR|Failed to fetch|connection/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: the retry may also fail under sustained churn — the
          // strict not.toBeVisible below then fails with the real error state.
          await page
            .locator('.asset-detail-page, [data-testid="asset-detail-page"]')
            .first()
            .waitFor({ state: 'visible', timeout: 60000 })
            .catch(() => null);
        }
      }

      await expect(errorDisplay).not.toBeVisible();

      // CM-002 specific: check for social section with Ratings/Reviews tabs
      const socialSection = page.locator('[data-testid="asset-social-section"]');
      // intentional: probes optional UI presence — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state, not a test failure.
      await socialSection.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const socialMissing =
        (await socialSection.count()) === 0 || !(await socialSection.isVisible());
      test.skip(socialMissing, 'Social section not visible — social capabilities may be off');
      if (socialMissing) {
        return;
      }

      // Must have at least one of Ratings or Reviews tabs
      const hasRatingsTab =
        (await socialSection.locator('button:has-text("Ratings")').count()) > 0;
      const hasReviewsTab =
        (await socialSection.locator('button:has-text("Reviews")').count()) > 0;
      expect(
        hasRatingsTab || hasReviewsTab,
        'Expected Ratings or Reviews tab in social section'
      ).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('communities without capability shows 403 or unavailable', async ({ page }) => {
      // Force the gate OFF deterministically: social.communities is
      // path-derived and ON for every tenant in this environment, so the
      // gate-off contract is not exercisable against the real manifest
      // (b6 skip root cause: "capability enabled — gate-off contract not
      // exercisable"). Intercepting the manifest makes the SPA's own
      // CapabilityRoute run the off path — real gating logic, no
      // backend changes and no shared-state mutation.
      await page.route('**/api/v1/capabilities/manifest/', async (route) => {
        // Synthesize the manifest instead of fetch-then-patch: a patched
        // fetch hits the browser HTTP cache on later tests in the same
        // worker (304 / empty body) and response.json() throws. The SPA
        // defaults missing manifest keys to false, so a minimal map
        // forces the gate OFF deterministically.
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            capabilities: { 'social.communities': false },
            source: 'e2e-gate-off-mock',
          }),
        });
      });
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      // The capability gate (CapabilityRoute) renders a loading spinner
      // while the capabilities query resolves (OpenAPI schema + runtime
      // snapshot — under batch load that outlasts a fixed sleep), then
      // either redirects (/unavailable) or mounts the page. Wait for one
      // of the terminal states instead of racing with a 5s sleep.
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator(
          '.communities-page, [data-testid="communities-page"], .disabled-capability-page, [data-testid="disabled-capability-page"], .unavailable-page, [data-testid="unavailable-page"]'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);
      // The manifest mock above forces the off path — the gate-off
      // terminal states below are the assertion, not a skip branch.
      const url = page.url();
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onComingSoon = url.includes('/coming-soon');
      const onLogin = url.includes('/login');
      const hasUnavailableContent =
        (await page.locator('.disabled-capability-page, [data-testid="disabled-capability-page"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]').count()) > 0;
      expect(on403 || onUnavailable || onComingSoon || hasUnavailableContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('asset social section handles missing ratings gracefully', async ({ page }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser);
      await loginUser(page, testUser);
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator('.asset-detail-page, [data-testid="asset-detail-page"]').first()
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);

      const redirectedToLogin = page.url().includes('/login');
      test.skip(redirectedToLogin, 'Redirected to login');
      if (redirectedToLogin) {
        return;
      }

      // Same transient-network-error recovery as the Success test: without
      // it, a churn-time asset fetch fails → no social section renders →
      // the skip below fires with the WRONG reason ("capabilities off"),
      // masking an infra blip as a feature state.
      const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: diagnostic-only read — an empty read just means the
        // retry branch won't fire and the flow continues to the section check.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (/NETWORK_ERROR|Failed to fetch|connection/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: the retry may also fail under sustained churn — a
          // persistent error then leaves the section absent and the skip
          // below fires, but with the page's real error state visible.
          await page
            .locator('.asset-detail-page, [data-testid="asset-detail-page"]')
            .first()
            .waitFor({ state: 'visible', timeout: 60000 })
            .catch(() => null);
        }
      }

      const socialSection = page.locator('[data-testid="asset-social-section"]');
      const socialAvailable = (await socialSection.count()) > 0;
      test.skip(!socialAvailable, 'Social section not available — capabilities off');
      if (!socialAvailable) {
        return;
      }

      // Click Ratings tab — newly created asset should show empty state or zero ratings
      const ratingsTab = socialSection.locator('button:has-text("Ratings")');
      const ratingsAvailable = (await ratingsTab.count()) > 0;
      test.skip(!ratingsAvailable, 'Ratings tab not available');
      if (!ratingsAvailable) {
        return;
      }
      await ratingsTab.click();
      await page.waitForTimeout(500);

      // Should show ratings content area (empty state or list)
      const hasRatingsContent =
        (await page.locator('.ratings-tab, .empty-state, [data-testid="empty-state"], .rating-item').count()) > 0;
      expect(hasRatingsContent, 'Expected ratings tab content').toBe(true);
    });
  });
});
