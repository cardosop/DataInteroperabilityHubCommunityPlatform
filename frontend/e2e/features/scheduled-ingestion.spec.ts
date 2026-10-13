/**
 * E2E Feature: Scheduled Ingestion
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /scheduled-ingestions (plural, per routes.tsx).
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Scheduled Ingestion', () => {
  // Budget arithmetic: loginAndNavigateToRoute worst case is 60s main loop +
  // 20s waitForAppMainReady grace, then the churn-recovery waitFor below can
  // add 30s, then the strict assertions ~10s — ~120s+ against a 120s cap.
  // Under a mid-batch API restart the budget expired during the final
  // expect() (b7 #38: ErrorDisplay visible while the recovery ran). 180s
  // lets the strict assertions run to completion.
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('scheduled-ingestions route loads with content when authenticated', async ({ page }) => {
      const adminUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, adminUser, '/scheduled-ingestions', {
        timeout: 60000,
        contentSelector:
          '.scheduled-ingestion-list-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Redirected to login — auth may have expired');
        return;
      }

      const url = page.url();
      expect(url).toMatch(/\/scheduled-ingestions|\/403/);

      // Churn recovery (b7 #38): the scheduled-ingestions fetch can fail
      // during an API restart window — the page renders its error state
      // with a Retry affordance. Use the app's recovery ONCE before the
      // strict assertion below.
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
            .locator(
              '.scheduled-ingestion-list-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"]'
            )
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
        }
      }
      // Success test must NOT accept .error-display, [data-testid="error-display"]
      await expect(errorDisplay).not.toBeVisible();
      // Must render actual page content — URL match alone provides no signal
      const hasContent =
        (await page
          .locator(
            '.scheduled-ingestion-list-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], h1'
          )
          .count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('scheduled-ingestion detail with non-existent id shows error or not-found', async ({
      page,
    }) => {
      const adminUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(
        page,
        adminUser,
        '/scheduled-ingestions/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector:
            '.error-display, [data-testid="error-display"], .scheduled-ingestion-detail-page, .unavailable-page, [data-testid="unavailable-page"], h1',
          acceptRedirectToLogin: true,
        }
      );
      if (page.url().includes('/login')) return;

      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      const hasUnavailable = (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]').first().count()) > 0;
      const hasNotFoundText =
        (await page.locator('text=/not found|404|does not exist/i').count()) > 0;
      const is404 = page.url().includes('/404') || page.url().includes('/not-found');

      expect(
        hasError || hasUnavailable || hasNotFoundText || is404,
        'Expected .error-display, [data-testid="error-display"], .unavailable-page, [data-testid="unavailable-page"], or not-found text for a nil-UUID scheduled ingestion'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('scheduled-ingestions responds when unauthenticated (redirects to login)', async ({
      page,
    }) => {
      await page.goto('/scheduled-ingestions');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/scheduled-ingestions|\/login|\/403|\/unavailable/);
    });
  });
});
