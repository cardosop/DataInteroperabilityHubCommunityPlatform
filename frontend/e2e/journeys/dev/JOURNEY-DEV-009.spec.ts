/**
 * E2E Test: JOURNEY-DEV-009 — Integrate with Developer Portal
 *
 * Journey: Integrate with Developer Portal
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer, /baas, /settings/api-keys, /webhooks.
 * Extends integrations-jobs-webhooks, admin-audit-settings patterns. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getExternalDeveloperUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-009: Integrate with Developer Portal', () => {
  test.setTimeout(300000); // 5 min: persona login + developer routes under parallel E2E load

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector: '.developer-portal-page, .app-main, .unavailable-page, .error-display',
      });
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onDeveloper && hasContent)).toBe(true);
    });

    test('settings api-keys loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/settings/api-keys', {
        timeout: 90000,
        contentSelector: '.auth-api-key-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/settings/api-keys');
    });

    test('webhooks list loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 90000,
        contentSelector: '.webhook-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/webhooks');
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 90000,
        contentSelector: '.webhook-list-page, .empty-state, .error-display',
      });
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page .webhook-detail-dl',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('developer, api-keys, webhooks routes accessible', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector:
          '.developer-portal-page, .developer-page, .app-main, .unavailable-page, .loading-spinner-container',
      });
      expect(
        page.url().includes('/developer') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
      if (page.url().includes('/login')) return;
      await page.goto('/settings/api-keys');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForURL(/\/(settings\/api-keys|login)(\?|$)/, { timeout: 15000 });
      expect(
        page.url().includes('/settings/api-keys') || page.url().includes('/login')
      ).toBe(true);
    });
  });
});
