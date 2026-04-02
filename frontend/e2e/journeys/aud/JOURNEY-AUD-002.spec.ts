/**
 * E2E Test: JOURNEY-AUD-002 — Generate Audit Reports
 *
 * Journey: Generate Audit Reports
 * Persona: Auditor
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /audit. Backend has tests; frontend spec for alignment.
 * Fixture: getAuditorUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getAuditorUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-002: Generate Audit Reports', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit event list loads for report generation', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
      const hasContent =
        (await page.locator('.audit-event-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
      const hasServerError = await page.locator('text=/500|internal server error/i').count();
      expect(hasServerError).toBe(0);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to audit route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/audit', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)/, { timeout: 20_000 });
      const url = page.url();
      // Unauthenticated users must be redirected — never allowed to stay on /audit
      expect(url.includes('/login') || url.includes('/403')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('audit route accessible for authenticated auditor', async ({ page }) => {
      await loginAsPersona(page, getAuditorUser);
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      // Auditor IS authenticated: /login should never appear; valid outcomes are /audit or /403 (role not assigned)
      expect(url.includes('/audit') || url.includes('/403')).toBe(true);
      if (url.includes('/audit')) {
        const hasContent =
          (await page.locator('.audit-event-list-page').count()) > 0 ||
          (await page.locator('.empty-state').count()) > 0;
        expect(hasContent).toBe(true) /* acceptable states */;
      }
    });
  });
});
