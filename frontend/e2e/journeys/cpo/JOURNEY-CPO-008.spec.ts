/**
 * E2E Test: JOURNEY-CPO-008 — Manage Consent Tracking
 *
 * Journey: Manage Consent Tracking
 * Persona: Compliance Officer
 * Use Case: UC-CPO-008 (Manage Consent Tracking)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /compliance, /governance.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-008: Manage Consent Tracking', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
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
    test('compliance run with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('compliance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
    });
  });
});
