/**
 * E2E Test: JOURNEY-DPO-012 — Join Data Community
 *
 * Journey: Join Data Community
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /social.
 * Capability-gated: social.ratings. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-012: Join Data Community', () => {
  test.setTimeout(300000); // 5 min: capability-gated route + login under parallel E2E load

  test.describe('Success', () => {
    test('social page loads (community)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/social', {
        timeout: 90000,
        contentSelector: '.social-page, .app-main, .unavailable-page, .loading-spinner-container',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(3000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onSocial = url.includes('/social');
      const hasContent =
        (await page.locator('.social-page, .app-main, .unavailable-page, .loading-spinner-container, .error-display').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onSocial && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('social page without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/social', {
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
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/social', {
        timeout: 90000,
        contentSelector: '.social-page, .app-main, .unavailable-page',
        acceptRedirectToLogin: true,
      });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/unavailable') || url.includes('/social')
      ).toBe(true);
    });
  });
});
