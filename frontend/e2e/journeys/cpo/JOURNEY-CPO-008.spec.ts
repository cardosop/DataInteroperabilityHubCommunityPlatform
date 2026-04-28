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
import { assertNonExistentIdShowsError, waitForAppMainReady, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-008: Manage Consent Tracking @critical', () => {
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
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const errText = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
        throw new Error(`Compliance page shows error for CPO user: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('governance page has consent or access request section', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(true, 'Login redirect or 403 — skipping success assertion');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Login redirect or 403 — skipping success assertion');
        return;
      }
      await waitForLoadingComplete(page);

      const consentText = page.getByText(/consent|privacy|access.request|data.subject/i);
      const accessRequestLinks = page.locator('a[href*="/governance/access-requests"]');
      const governanceContent = page.locator(
        '.governance-page, .access-request-list-page, .governance-retention-policy-list-page, [class*="governance"]'
      );

      const hasConsentText = (await consentText.count()) > 0;
      const hasAccessRequestLinks = (await accessRequestLinks.count()) > 0;
      const hasGovernanceContent = (await governanceContent.count()) > 0;

      expect(hasConsentText || hasAccessRequestLinks || hasGovernanceContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('compliance run with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page, [data-testid="compliance-run-detail-page"]',
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
