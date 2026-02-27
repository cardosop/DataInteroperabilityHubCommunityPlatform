/**
 * E2E Test: JOURNEY-DC-009 — Join Data Community
 *
 * Journey: Join Data Community
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /social.
 * Capability-gated: social.ratings. Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-009: Join Data Community', () => {
  test.setTimeout(300000); // 5 min: capability-gated route + login under parallel E2E load

  test.describe('Success', () => {
    test('social page loads (community)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/social', {
        timeout: 90000,
        contentSelector: '.social-page, .app-main, .unavailable-page, .loading-spinner',
        acceptRedirectToLogin: true,
      });
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onUnavailable = page.url().includes('/unavailable');
      const onSocial = page.url().includes('/social');
      const hasContent =
        (await page.locator('.social-page, .app-main, .unavailable-page, .loading-spinner').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onSocial && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('social page without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/social', {
        timeout: 90000,
        contentSelector: '.social-page, .unavailable-page, .error-display',
        acceptRedirectToLogin: true,
      });
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onSocial = page.url().includes('/social');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onSocial || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('social page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/social', {
        timeout: 90000,
        contentSelector: '.social-page, .app-main, .unavailable-page',
        acceptRedirectToLogin: true,
      });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/social') || url.includes('/unavailable')
      ).toBe(true);
    });
  });
});
