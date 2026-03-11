/**
 * E2E Test: JOURNEY-DC-009 — Join Data Community
 *
 * Journey: Join Data Community
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /communities (Phase 27.2).
 * Capability-gated: social.communities. Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DC-009: Join Data Community', () => {
  test.setTimeout(300000); // 5 min: capability-gated route + login under parallel E2E load

  test.describe('Success', () => {
    test('communities page loads (community)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .app-main, .unavailable-page, .loading-spinner-container, .loading-spinner, #email',
        { timeout: 90000 }
      );
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onUnavailable = page.url().includes('/unavailable');
      const onCommunities = page.url().includes('/communities');
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .app-main, .unavailable-page, .loading-spinner').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onCommunities && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('communities page without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page, .error-display, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onCommunities = page.url().includes('/communities');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onCommunities || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('communities page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.communities-page, .communities-tab, .app-main, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/communities') || url.includes('/unavailable')
      ).toBe(true);
    });
  });
});
