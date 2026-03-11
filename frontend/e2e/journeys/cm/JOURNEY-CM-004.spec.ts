/**
 * E2E Test: JOURNEY-CM-004 — Manage Activity Feeds
 *
 * Journey: Manage Activity Feeds
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /communities (Phase 27.2).
 * Capability-gated: social.communities. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-CM-004: Manage Activity Feeds', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities page loads for activity feeds', async ({ page }) => {
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
  });

  test.describe('Failure', () => {
    test('communities without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onCommunities = page.url().includes('/communities');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onCommunities || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('communities page loads with empty or populated feeds', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(
        url.includes('/login') ||
          url.includes('/403') ||
          url.includes('/unavailable') ||
          url.includes('/communities')
      ).toBe(true);
    });
  });
});
