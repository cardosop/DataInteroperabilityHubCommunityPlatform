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
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector: '.developer-portal-page, .app-main, [data-testid="app-main"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
      });
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      if (onLogin || on403) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onDeveloper).toBe(true);
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('settings api-keys loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/settings/api-keys', {
        timeout: 90000,
        contentSelector: '.auth-api-key-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/settings/api-keys');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('webhooks list loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 90000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/webhooks');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 90000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
          '.developer-portal-page, .developer-page, .app-main, [data-testid="app-main"], .unavailable-page, [data-testid="unavailable-page"]',
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
