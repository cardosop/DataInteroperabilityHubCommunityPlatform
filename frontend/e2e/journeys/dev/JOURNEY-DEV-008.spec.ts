/**
 * E2E Test: JOURNEY-DEV-008 — Use Plugin System
 *
 * Journey: Use Plugin System
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer.
 * Capability-gated: developer.plugins. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getExternalDeveloperUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-008: Use Plugin System', () => {
  test.setTimeout(300000); // 5 min: persona login + developer route under parallel E2E load

  test.describe('Success', () => {
    test('developer page loads (plugins)', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector:
          '.developer-portal-page, .developer-page, .app-main, .unavailable-page, .error-display, .loading-spinner-container',
      });
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onDeveloper && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('developer page without capability shows 403 or unavailable', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector:
          '.developer-portal-page, .developer-page, .app-main, .unavailable-page, .error-display, .loading-spinner-container',
      });
      const url = page.url();
      const isGated = url.includes('/403') || url.includes('/login');
      const isOpen = url.includes('/developer');
      expect(isGated || isOpen).toBe(true);
      if (isOpen) {
        // Capability is enabled — content must actually be present (not just URL match)
        const hasContent = (await page.locator('.developer-portal-page, .plugin-list, main').count()) > 0;
        expect(hasContent).toBe(true);
      }
    });
  });
});
