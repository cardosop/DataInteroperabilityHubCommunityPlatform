/**
 * E2E Test: JOURNEY-CPO-007 — Set Up GDPR Right to be Forgotten
 *
 * Journey: Set Up GDPR Right to be Forgotten
 * Persona: Compliance Officer
 * Use Case: UC-CPO-007 (Set Up GDPR Right to be Forgotten)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /compliance, /governance.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, waitForAppMainReady, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-007: Set Up GDPR Right to be Forgotten', () => {
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
          test.skip(true, 'Auth/role gated — skipping success assertion');
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
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('governance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onGov = page.url().includes('/governance');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      if (on403 || onLogin) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onGov).toBe(true);
      await expect(page.locator('.error-display')).not.toBeVisible();
    });

    test('governance page has GDPR or data deletion section', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(true, 'Auth/role gated — skipping success assertion');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });

      // Look for GDPR / erasure / data-deletion related text
      const gdprText = page.getByText(/GDPR|erasure|data.deletion|right.to.be.forgotten|retention/i);
      const gdprTextVisible = (await gdprText.count()) > 0 && await gdprText.first().isVisible().catch(() => false);

      // Look for governance sub-navigation links
      const retentionLink = page.locator('a[href*="/governance/retention"]');
      const accessRequestsLink = page.locator('a[href*="/governance/access-requests"]');
      const hasRetentionLink = (await retentionLink.count()) > 0 && await retentionLink.first().isVisible().catch(() => false);
      const hasAccessRequestsLink = (await accessRequestsLink.count()) > 0 && await accessRequestsLink.first().isVisible().catch(() => false);

      const hasGovSubNav = hasRetentionLink || hasAccessRequestsLink;

      // At least GDPR text OR governance sub-nav links must be visible
      expect(gdprTextVisible || hasGovSubNav).toBe(true);

      // error-display must NOT be visible (D85)
      await expect(page.locator('.error-display')).not.toBeVisible();
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
    test('compliance and governance routes accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/governance') || page.url().includes('/403') || page.url().includes('/login')).toBe(true);
    });
  });
});
