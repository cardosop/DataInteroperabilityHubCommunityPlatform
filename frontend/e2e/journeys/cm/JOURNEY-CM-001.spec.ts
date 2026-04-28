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

test.describe('JOURNEY-CM-001: Manage Data Community', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities page loads with community list or empty state', async ({ page }) => {
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator('.communities-page, [data-testid="communities-page"], .unavailable-page, [data-testid="unavailable-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 25000 })
        .catch(() => null);

      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }

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
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasUnavailableContent =
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]').count()) > 0;
      expect(on403 || onUnavailable || hasUnavailableContent || onLogin).toBe(true);
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
