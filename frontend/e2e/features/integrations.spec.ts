/**
 * E2E Feature: Integrations
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /integrations/connections, /integrations/sync-jobs, /integrations/mappings.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Integrations', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections loads or redirects to login', async ({ page }) => {
      await page.goto('/integrations/connections');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/integrations');
    });
  });

  test.describe('Failure', () => {
    test('integrations sync-jobs loads content or shows gated/error state', async ({ page }) => {
      await page.goto('/integrations/sync-jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      // URL check alone is trivially true here (navigating to /integrations/sync-jobs and
      // staying there always matches /integrations). Assert page-level content instead.
      if (url.includes('/login') || url.includes('/403')) {
        // Redirected — acceptable for role-gated route
        expect(url).toMatch(/\/login|\/403/);
        return;
      }
      // Must render actual page state — not just a URL match
      const hasContent =
        (await page
          .locator(
            '.integration-sync-jobs-page, .sync-jobs-page, .empty-state, .unavailable-page, h1'
          )
          .count()) > 0;
      const hasError = (await page.locator('.error-display').count()) > 0;
      expect(
        hasContent || hasError,
        'Expected page content (.sync-jobs-page, .empty-state, .unavailable-page, h1, or .error-display)'
      ).toBe(true);
    });
  });
});
