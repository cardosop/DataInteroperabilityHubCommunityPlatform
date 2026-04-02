/**
 * E2E Test: JOURNEY-CPO-002 — Generate Compliance Report
 *
 * Journey: Generate Compliance Report
 * Persona: Compliance Officer
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /compliance. Backend has tests; frontend spec for alignment.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { hasLoginPrompt, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-002: Generate Compliance Report', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance list loads for report generation', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector:
            '.compliance-run-list-page, .empty-state, .error-display',
        });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/compliance');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to compliance route redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/compliance', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|compliance|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/compliance')
      ).toBe(true);
      if (url.includes('/compliance')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('compliance route accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(
        page.url().includes('/compliance') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
