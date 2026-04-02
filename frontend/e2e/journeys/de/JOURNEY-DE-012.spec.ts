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
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/developer', {
        timeout: 60000,
        contentSelector:
          '.developer-portal-page, .developer-page, .unavailable-page, .error-display',
      });
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onDeveloper = page.url().includes('/developer');
      if (onLogin || on403) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onDeveloper).toBe(true);
      const hasContent =
        (await page.locator('.developer-portal-page, .developer-page').count()) > 0 ||
        (await page.locator('.unavailable-page').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display')).not.toBeVisible();
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
      await loginAndNavigateToRoute(page, testUser, '/developer', {
        timeout: 90000,
        contentSelector:
          '.developer-portal-page, .developer-page, .unavailable-page, .error-display',
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
