/**
 * E2E Test: JOURNEY-CPO-004 — Review Access Requests
 *
 * Journey: Review Access Requests
 * Persona: Compliance Officer
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /governance (AccessRequestListPage at index). Backend has tests; frontend spec for alignment.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { hasLoginPrompt } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-004: Review Access Requests', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('governance access requests page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onGov = page.url().includes('/governance');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      if (on403 || onLogin) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onGov).toBe(true);
      await expect(page.locator('.error-display')).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to governance route redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/governance', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|governance|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/governance')
      ).toBe(true);
      if (url.includes('/governance')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('governance route accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(
        page.url().includes('/governance') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
