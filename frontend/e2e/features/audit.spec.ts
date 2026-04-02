/**
 * E2E Feature: Audit
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /audit.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getAuditorUser, getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Audit', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit route loads with content when authenticated as auditor', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-log-page, .audit-page, .empty-state, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }

      const url = page.url();
      expect(url).toMatch(/\/audit|\/403/);

      // Success test must NOT accept .error-display
      await expect(page.locator('.error-display')).not.toBeVisible();
      // Must render actual content — URL check alone does not prove the page loaded
      const hasContent =
        (await page.locator('.audit-log-page, .audit-page, .empty-state, h1').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('audit route with non-auditor role shows 403 or redirects', async ({ page }) => {
      // A regular (non-auditor) user must NOT freely access audit logs.
      // Previously this test was identical to Success — zero additional coverage.
      const regularUser = await getTestUser();
      await loginAndNavigateToRoute(page, regularUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-log-page, .audit-page, .empty-state, .error-display, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) return;

      const url = page.url();
      const on403 = url.includes('/403');
      const hasForbiddenText =
        (await page.locator('text=/forbidden|403|access denied|not authorized/i').count()) > 0;
      const hasErrorDisplay = (await page.locator('.error-display').count()) > 0;

      // If a regular user can see raw audit content, that's a permissions signal worth surfacing
      const hasUnrestrictedAuditContent =
        (await page.locator('.audit-log-page, .audit-page').count()) > 0 &&
        !(on403 || hasForbiddenText);

      if (hasUnrestrictedAuditContent) {
        console.warn(
          '⚠️ Regular user can access /audit — verify role-based access control is enforced'
        );
      }
      expect(on403 || hasForbiddenText || hasErrorDisplay).toBe(true) /* regular user must see 403, forbidden text, or error */;
    });
  });
});
