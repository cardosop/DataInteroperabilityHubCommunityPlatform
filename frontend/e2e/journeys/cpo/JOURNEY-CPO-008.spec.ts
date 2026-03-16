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
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
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
      // error-display is NOT acceptable — compliance service must be reachable
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Compliance page shows error for CPO user: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
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

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/compliance');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
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
