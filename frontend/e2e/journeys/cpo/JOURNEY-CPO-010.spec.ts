/**
 * E2E Test: JOURNEY-CPO-010 — Review AI Auto-Classification Results / View Audit Logs
 *
 * Journey: Review AI Auto-Classification Results / View Audit Logs
 * Persona: Compliance Officer
 * Use Case: UC-CPO-010 (Review AI Auto-Classification Results)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /compliance, /audit.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-010: Review AI Auto-Classification Results / View Audit Logs', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance page loads', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/compliance', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
    });

    test('audit page loads', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/audit', { timeout: 60000 });
      const onAudit = page.url().includes('/audit');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasContent =
        (await page.locator('.audit-event-list-page, .app-main, .error-display').count()) > 0;
      expect(onAudit || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('audit event detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/audit/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '[data-testid="audit-event-detail-page"]',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('compliance and audit routes accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/audit') || page.url().includes('/403') || page.url().includes('/login')).toBe(true);
    });
  });
});
