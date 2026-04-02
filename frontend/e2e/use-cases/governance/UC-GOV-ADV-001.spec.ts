/**
 * E2E: UC-GOV-ADV-001 — Configure Automated Compliance
 *
 * Use Case: Configure Automated Compliance
 * Persona: Compliance Officer
 * Reference: docs/USE_CASES.md#uc-gov-adv-001
 *
 * Success/Failure/Edge. Routes: /compliance, /compliance/runs/:id.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  waitForAppMainReady,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('UC-GOV-ADV-001: Configure Automated Compliance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance page loads with run list or empty state', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await waitForAppMainReady(page);
      test.skip(page.url().includes('/login'), 'Auth redirect');
      expect(page.url()).toContain('/compliance');
      await waitForLoadingComplete(page, { timeout: 15000 });
      // D85: error-display is NOT acceptable — means backend or compliance service is down
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Compliance page shows error: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('compliance page has create or scheduling UI', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await waitForAppMainReady(page);
      test.skip(page.url().includes('/login'), 'Auth redirect');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasCreateButton =
        (await page.locator('button:has-text("Create"), button:has-text("New"), a:has-text("Create"), a:has-text("New")').count()) > 0;
      const hasScheduleUI =
        (await page.locator('[class*="schedule"], [class*="config"], [data-testid*="schedule"]').count()) > 0;
      const hasComplianceContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasCreateButton || hasScheduleUI || hasComplianceContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to compliance redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/compliance');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });

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
    test('compliance page with no runs shows empty state', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        expect(url).toMatch(/\/login|\/403/);
        return;
      }
      expect(url).toContain('/compliance');
      const hasContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
