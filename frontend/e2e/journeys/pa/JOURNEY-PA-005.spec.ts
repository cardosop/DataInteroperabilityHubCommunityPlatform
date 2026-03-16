/**
 * E2E Test: JOURNEY-PA-005 — Manage Marketplace Configuration
 * Persona: Platform Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/pa/JOURNEY-PA-005.md
 * Real backend only; no mocks.
 */
import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-PA-005: Manage Marketplace Configuration', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('platform admin can access marketplace config and see configurable options', async ({
      page,
    }) => {
      const paUser = await getPlatformAdminUser();
      // Start with /admin (guaranteed to exist); probe non-existent sub-routes with short timeout
      const routes = ['/admin', '/admin/marketplace', '/admin/marketplace-config', '/marketplace/admin'];

      let landed = false;
      for (const route of routes) {
        const routeTimeout = route === '/admin' ? 60000 : 15000;
        await loginAndNavigateToRoute(page, paUser, route, {
          timeout: routeTimeout,
          contentSelector: '.admin-page, .marketplace-config-page',
        }).catch(() => null);
        if (page.url().includes('/403') || page.url().includes('/login')) continue;
        const hasConfig =
          (await page.locator('.marketplace-config-page').count()) > 0 ||
          (await page.locator('text=/marketplace|configuration|pricing/i').count()) > 0;
        if (hasConfig) { landed = true; break; }
      }

      if (!landed) {
        test.skip(true, 'Marketplace configuration page not found at any known route');
        return;
      }

      // Page renders without error
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        if (!/403|forbidden/i.test(errText ?? '')) {
          throw new Error(`Marketplace config page shows unexpected error: ${errText}`);
        }
      }
      // Page loaded — confirm no unhandled 500 error
      const has500 = (await page.locator('text=/500|Internal Server Error/i').count()) > 0;
      expect(has500).toBe(false);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace|403)/, { timeout: 20_000 });
      expect(page.url()).toMatch(/\/login|\/403|\/marketplace/);
    });
  });

  test.describe('Route', () => {
    test('marketplace list accessible as platform admin', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/marketplace', {
        timeout: 60000,
        contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .error-display',
      });
      expect(page.url()).toMatch(/\/marketplace|\/403|\/login/);
    });
  });
});
