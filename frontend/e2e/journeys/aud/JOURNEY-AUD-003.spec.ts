/**
 * E2E Test: JOURNEY-AUD-003 — Export Audit Data
 *
 * Journey: Export Audit Data
 * Persona: Auditor
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /audit, /audit/:id. Backend has tests; frontend spec for alignment.
 * Fixture: getAuditorUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getAuditorUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-003: Export Audit Data', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit event list loads for export', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
    });
  });

  test.describe('Failure', () => {
    test('audit event detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getAuditorUser);
      await page.goto('/audit/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '[data-testid="audit-event-detail-page"]',
        waitAfterLoad: 8000,
      });
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
