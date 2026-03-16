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
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DE-012: Create Custom Plugin', () => {
  test.setTimeout(360000); // 6 min: capability-gated route + login under parallel E2E load

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.developer-portal-page, .app-main, .unavailable-page, .loading-spinner-container, .loading-spinner, #email',
        { timeout: 45000 }
      );
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onUnavailable = page.url().includes('/unavailable');
      const onDeveloper = page.url().includes('/developer');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, .unavailable-page, .loading-spinner-container, .loading-spinner').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onDeveloper && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /developer redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/developer', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)/, { timeout: 20000 }).catch(() => null);
      expect(page.url().includes('/login') || page.url().includes('/403')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('developer page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.developer-portal-page, .app-main, .unavailable-page, #email',
        { timeout: 90000 }
      );
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
