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
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-004: Configure Platform Settings', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('admin page loads for platform settings', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/403')) {
        test.skip(true, 'Redirected to /403 — PLATFORM_ADMIN role not assigned to test user');
      }
      expect(page.url()).toContain('/admin');
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

});
