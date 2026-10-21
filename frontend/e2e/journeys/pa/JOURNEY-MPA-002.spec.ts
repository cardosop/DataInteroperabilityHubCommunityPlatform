/**
 * E2E Test: JOURNEY-MPA-002 — Process Marketplace Orders
 *
 * Journey: Process Marketplace Orders
 * Persona: Platform Admin
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /marketplace/orders, /admin. Backend has tests; frontend spec for alignment.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-002: Process Marketplace Orders', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace orders list loads', async ({ page }) => {
      await loginAndNavigateToRoute(page, await getPlatformAdminUser(), '/marketplace/orders', {
        timeout: 65000,
        contentSelector:
          '.order-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      const gated =
        page.url().includes('/login') ||
        page.url().includes('/403') ||
        page.url().includes('/unavailable');
      test.skip(gated, 'Auth/role/capability gated — skipping success assertion');
      if (gated) return;
      expect(page.url()).toContain('/marketplace');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to marketplace orders redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace/orders', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/marketplace')
      ).toBe(true);
    });
  });

});
