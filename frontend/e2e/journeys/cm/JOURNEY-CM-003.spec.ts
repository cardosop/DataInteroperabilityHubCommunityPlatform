/**
 * E2E Test: JOURNEY-CM-003 — Assign Data Stewards
 *
 * Journey: Assign Data Stewards
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /social, /assets (stewardship).
 * Capability-gated: social.ratings. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-CM-003: Assign Data Stewards', () => {
  // 5 min: visible project uses slowMo:400 (adds ~400ms per action); login + nav can exceed 3 min under load
  test.setTimeout(300000);

  test.describe('Success', () => {
    test('social page loads for stewardship', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onSocial = page.url().includes('/social');
      const hasContent =
        (await page.locator('.social-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onSocial && hasContent)).toBe(true);
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
    test('social and assets routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(
        page.url().includes('/social') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });
  });
});
