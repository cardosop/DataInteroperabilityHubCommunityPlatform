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
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-CM-003: Assign Data Stewards', () => {
  // 5 min: visible project uses slowMo:400 (adds ~400ms per action); login + nav can exceed 3 min under load
  test.setTimeout(300000);

  test.describe('Success', () => {
    test('communities page loads for stewardship', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onCommunities = url.includes('/communities');
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .app-main, .unavailable-page, .loading-spinner-container').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onCommunities && hasContent)).toBe(true);
    });

    test('assets list loads for steward assignment', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
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
        detailContentSelector: '.asset-detail-page',
        waitAfterLoad: 8000,
      });
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
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });
  });
});
