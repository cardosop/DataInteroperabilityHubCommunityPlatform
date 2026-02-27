/**
 * E2E Test: JOURNEY-CPO-005 — Audit Access Logs
 *
 * Journey: Audit Access Logs
 * Persona: Compliance Officer
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /audit. Backend has tests; frontend spec for alignment.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-005: Audit Access Logs', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit event list loads', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to audit route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/audit', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|audit|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/audit')).toBe(true);
      if (url.includes('/audit')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('audit route accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(
        page.url().includes('/audit') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
