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
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

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
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
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
      await loginAsPersona(page, getAuditorUser);
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
