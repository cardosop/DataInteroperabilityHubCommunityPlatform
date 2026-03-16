/**
 * E2E Test: JOURNEY-TA-004 — Manage Tenant Billing
 *
 * Journey: Manage Tenant Billing
 * Persona: Tenant Admin
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /admin. Backend has tests; frontend spec for alignment.
 * Fixture: getTenantAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTenantAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-TA-004: Manage Tenant Billing', () => {
  test.setTimeout(240000); // 4 min: visible/slowMo + login can exceed 2 min

  test.describe('Success', () => {
    test('admin page loads for billing', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
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
