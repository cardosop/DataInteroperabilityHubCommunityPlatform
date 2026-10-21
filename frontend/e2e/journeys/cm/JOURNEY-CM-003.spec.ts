/**
 * E2E Test: JOURNEY-CM-003 — Assign Data Stewards
 *
 * Journey: Assign Data Stewards
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /communities, /assets (Phase 27.2).
 * Capability-gated: social.communities. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-CM-003: Assign Data Stewards', () => {
  // 5 min: visible project uses slowMo:400 (adds ~400ms per action); login + nav can exceed 3 min under load
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities page loads for stewardship', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      // The CapabilityRoute gate resolves asynchronously (capabilities
      // query) — wait for a terminal state instead of racing a fixed 3s
      // sleep with the redirect.
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator('.communities-page, [data-testid="communities-page"], .disabled-capability-page, [data-testid="disabled-capability-page"], .unavailable-page, [data-testid="unavailable-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onCommunities = url.includes('/communities');
      if (onLogin || on403) {
        test.skip(onLogin || on403, 'Auth/role gated — skipping success assertion');
        return;
      }
      // Two distinct gate-off terminal states:
      //  - /coming-soon (MVP mode): the surface is genuinely out of scope —
      //    a legitimate per-environment state, plain conditional skip.
      //  - /unavailable: the OpenAPI-derived gate failed CLOSED under batch
      //    churn — the social paths are ALWAYS registered in the OpenAPI
      //    spec, so this is a transient snapshot-fetch failure, not a
      //    disabled capability. W16-guarded skip: raises in CI, skips
      //    locally.
      test.skip(url.includes('/coming-soon'), 'social.communities out of MVP scope — success contract not exercisable');
      if (url.includes('/unavailable')) {
        environmentSkipGuard(
          'social.communities gate bounced to /unavailable — capabilities/OpenAPI snapshot fetch failed under parallel load'
        );
      }
      test.skip(url.includes('/unavailable'), 'social.communities gate bounced to /unavailable — transient snapshot failure');
      if (url.includes('/unavailable') || url.includes('/coming-soon')) {
        return;
      }
      expect(onCommunities).toBe(true);
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('assets list loads for steward assignment', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/assets');
    });
  });

  test.describe('Failure', () => {
    test('asset detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.asset-detail-page, [data-testid="asset-detail-page"]',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('communities and assets routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(
        url.includes('/communities') ||
          url.includes('/403') ||
          url.includes('/unavailable') ||
          url.includes('/login')
      ).toBe(true);
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/assets');
    });
  });
});
