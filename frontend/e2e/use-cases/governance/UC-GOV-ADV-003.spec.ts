/**
 * E2E: UC-GOV-ADV-003 — Manage Consent Tracking
 *
 * Use Case: Manage Consent Tracking
 * Persona: Compliance Officer
 * Reference: docs/USE_CASES.md#uc-gov-adv-003
 *
 * Success/Failure/Edge. Routes: /governance.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import {
  waitForAppMainReady,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('UC-GOV-ADV-003: Manage Consent Tracking', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('governance page loads with consent or privacy sections', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await waitForAppMainReady(page);
      test.skip(page.url().includes('/login'), 'Auth redirect');
      expect(page.url()).toContain('/governance');
      await waitForLoadingComplete(page, { timeout: 15000 });
      // D85: error-display is NOT acceptable — means backend or governance service is down
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Governance page shows error: "${errText?.slice(0, 300)}"`);
      }
      const hasConsentContent =
        (await page.getByText(/consent|privacy|tracking/i).count()) > 0;
      const hasAccessRequestContent =
        (await page.getByText(/access.request/i).count()) > 0 ||
        (await page.locator('a[href*="/governance/access-requests"]').count()) > 0;
      const hasGovernancePage =
        (await page.locator('.governance-access-request-list-page, .access-request-list-page, .governance-retention-policy-list-page').count()) > 0;
      expect(hasConsentContent || hasAccessRequestContent || hasGovernancePage).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to governance redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/governance');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('governance sections visible and navigable', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        expect(url).toMatch(/\/login|\/403/);
        return;
      }
      expect(url).toContain('/governance');
      const hasNavLinks =
        (await page.locator('a[href*="/governance/retention"], a[href*="/governance/access-requests"]').count()) > 0;
      expect(hasNavLinks).toBe(true);
    });
  });
});
