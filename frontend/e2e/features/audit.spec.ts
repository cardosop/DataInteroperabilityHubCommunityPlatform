/**
 * E2E Feature: Audit
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /audit.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getAuditorUser, getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Audit', () => {
  // Budget arithmetic: loginAndNavigateToRoute worst case is 60s main loop +
  // 20s waitForAppMainReady grace (POST_TIMEOUT_GRACE_MS), then the churn-
  // recovery waitFor below can add 30s, then the strict assertions ~10s.
  // That is ~120s+ against a 120s cap — under a mid-batch API restart the
  // budget expired DURING the final expect() and the browser was closed
  // ("Test timeout ... Target page, context or browser has been closed"),
  // masking the real assertion outcome (b7: audit Success test). 180s lets
  // the final expect() run to completion so a persistent error state fails
  // with the precise "element is visible" message instead of an opaque
  // budget-wall browser-close.
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('audit route loads with content when authenticated as auditor', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-log-page, .audit-page, .empty-state, [data-testid="empty-state"], h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Redirected to login — auth may have expired');
        return;
      }

      const url = page.url();
      expect(url).toMatch(/\/audit|\/403/);

      // Churn recovery: the audit list fetch can fail during an API restart
      // window — the page renders its error state with a Retry affordance.
      // Use the app's recovery ONCE before the strict D85 assertion below.
      const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: diagnostic-only read — an empty read just skips the
        // retry and the strict assertion below reports the visible state.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (/NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: the retry may also fail under sustained churn — the
          // strict not.toBeVisible below then fails with the real state.
          await page
            .locator('.audit-log-page, .audit-page, .empty-state, [data-testid="empty-state"]')
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
        }
      }
      // Success test must NOT accept .error-display, [data-testid="error-display"]
      await expect(errorDisplay).not.toBeVisible();
      // Must render actual content — URL check alone does not prove the page loaded
      const hasContent =
        (await page.locator('.audit-log-page, .audit-page, .empty-state, [data-testid="empty-state"], h1').count()) > 0;
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
        contentSelector: '.audit-log-page, .audit-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Auth session expired before RBAC check — not a valid RBAC result');
        return;
      }

      const url = page.url();
      const on403 = url.includes('/403');
      const hasForbiddenText =
        (await page.locator('text=/forbidden|403|access denied|not authorized/i').count()) > 0;
      const hasErrorDisplay = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;

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
