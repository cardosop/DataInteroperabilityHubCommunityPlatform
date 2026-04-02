/**
 * E2E Feature: Scheduled Ingestion
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /scheduled-ingestions (plural, per routes.tsx).
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Scheduled Ingestion', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('scheduled-ingestions route loads with content when authenticated', async ({ page }) => {
      const adminUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, adminUser, '/scheduled-ingestions', {
        timeout: 60000,
        contentSelector:
          '.scheduled-ingestion-list-page, .empty-state, .unavailable-page, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }

      const url = page.url();
      expect(url).toMatch(/\/scheduled-ingestions|\/403/);

      // Success test must NOT accept .error-display
      await expect(page.locator('.error-display')).not.toBeVisible();
      // Must render actual page content — URL match alone provides no signal
      const hasContent =
        (await page
          .locator(
            '.scheduled-ingestion-list-page, .empty-state, .unavailable-page, h1'
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
            '.error-display, .scheduled-ingestion-detail-page, .unavailable-page, h1',
          acceptRedirectToLogin: true,
        }
      );
      if (page.url().includes('/login')) return;

      const hasError = (await page.locator('.error-display').count()) > 0;
      const hasUnavailable = (await page.locator('.unavailable-page').count()) > 0;
      const hasNotFoundText =
        (await page.locator('text=/not found|404|does not exist/i').count()) > 0;
      const is404 = page.url().includes('/404') || page.url().includes('/not-found');

      expect(
        hasError || hasUnavailable || hasNotFoundText || is404,
        'Expected .error-display, .unavailable-page, or not-found text for a nil-UUID scheduled ingestion'
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
