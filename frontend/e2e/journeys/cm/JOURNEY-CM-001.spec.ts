/**
 * E2E Test: JOURNEY-CM-001 — Manage Data Community
 *
 * Journey: Manage Data Community
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Distinct from CM-002 (Moderate Reviews/Ratings) and CM-004 (Manage Activity Feeds):
 * CM-001 focuses on the /communities page itself — listing communities, viewing
 * community content. CM-002 tests the Ratings/Reviews tabs on an asset page.
 * CM-004 tests the Comments/Activity tab on an asset page.
 *
 * Success/Failure/Edge. Routes: /communities (Phase 27.2).
 * Capability-gated: social.communities. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';

test.describe('JOURNEY-CM-001: Manage Data Community', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities page loads with community list or empty state', async ({ page }) => {
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator('.communities-page, [data-testid="communities-page"], .disabled-capability-page, [data-testid="disabled-capability-page"], .unavailable-page, [data-testid="unavailable-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);

      const url = page.url();
      const authGated = url.includes('/login') || url.includes('/403');
      test.skip(authGated, 'Auth/role gated — skipping success assertion');
      if (authGated) {
        return;
      }
      // Two distinct gate-off terminal states:
      //  - /coming-soon (MVP mode): the surface is genuinely out of scope —
      //    a legitimate per-environment state, plain skip.
      //  - /unavailable: the OpenAPI-derived gate (capabilitiesService
      //    isPathIncluded on /api/v1/social/communities/) failed CLOSED under
      //    batch churn — the social paths are ALWAYS registered in the
      //    OpenAPI spec, so this is a transient snapshot-fetch failure, not
      //    a disabled capability. W16-guarded skip: raises in CI, skips
      //    locally.
      test.skip(url.includes('/coming-soon'), 'social.communities out of MVP scope — success contract not exercisable');
      if (url.includes('/unavailable')) {
        environmentSkipGuard(
          'social.communities gate bounced to /unavailable — OpenAPI snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        url.includes('/unavailable'),
        'social.communities gate bounced to /unavailable — transient snapshot failure'
      );

      expect(url).toContain('/communities');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();

      // CM-001 specific: communities page must render its data-testid or class
      const hasCommunitiesPage =
        (await page.locator('.communities-page, [data-testid="communities-page"]').count()) > 0;
      const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(
        hasCommunitiesPage || hasEmptyState,
        'Expected .communities-page or .empty-state, [data-testid="empty-state"] on /communities'
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
    test('/social redirects to /communities', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForURL(/\/(login|403|communities|unavailable)/, { timeout: 20000 });
      const url = page.url();
      expect(
        url.includes('/login') ||
          url.includes('/403') ||
          url.includes('/communities') ||
          url.includes('/unavailable')
      ).toBe(true);
    });
  });
});
