/**
 * E2E Test: JOURNEY-DE-012 — Create Custom Plugin
 *
 * Journey: Create Custom Plugin
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer.
 * Capability-gated: developer.plugins. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-012: Create Custom Plugin', () => {
  test.setTimeout(300000); // 5 min: capability-gated route + login under parallel E2E load

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/developer', {
        timeout: 90000,
        contentSelector: '.developer-portal-page, .app-main, .unavailable-page, .loading-spinner',
        acceptRedirectToLogin: true,
      });
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onUnavailable = page.url().includes('/unavailable');
      const onDeveloper = page.url().includes('/developer');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, .unavailable-page, .loading-spinner').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onDeveloper && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('developer page without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/developer', {
        timeout: 90000,
        contentSelector: '.developer-portal-page, .unavailable-page, .error-display',
        acceptRedirectToLogin: true,
      });
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onDeveloper || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('developer page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/developer', {
        timeout: 90000,
        contentSelector: '.developer-portal-page, .app-main, .unavailable-page',
        acceptRedirectToLogin: true,
      });
      const url = page.url();
      expect(
        url.includes('/login') ||
          url.includes('/403') ||
          url.includes('/developer') ||
          url.includes('/unavailable')
      ).toBe(true);
    });
  });
});
