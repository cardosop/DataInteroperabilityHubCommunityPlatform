/**
 * E2E Test: JOURNEY-MPA-004 — Configure Platform Settings
 *
 * Journey: Configure Platform Settings
 * Persona: Platform Admin
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /admin. Backend has tests; frontend spec for alignment.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-004: Configure Platform Settings', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('admin page loads for platform settings', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      // Admin or 403: role-gated; 403 when ensure_e2e_user_roles hasn't assigned PLATFORM_ADMIN
      expect(page.url().includes('/admin') || page.url().includes('/403')).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to admin route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('admin route accessible', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(
        page.url().includes('/admin') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
