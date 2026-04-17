/**
 * E2E Feature: Compliance
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /compliance, /compliance/runs/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute, waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Compliance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('compliance list loads: still on /login after loginAndNavigateToRoute');
      }
      await assertListPageLoads(page, '.compliance-run-list-page, .empty-state', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('compliance run detail with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000', { waitUntil: 'domcontentloaded', timeout: 60000 });
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch {
        // May resolve to error/login — acceptable
      }
      const url = page.url();
      const onLogin = url.includes('/login');
      // `onCompliance` was trivially true (we navigated to /compliance/runs/...) — removed.
      // The test must assert an actual error state, not just "the URL still contains /compliance".
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(
        onLogin || hasError,
        'Expected .error-display or not-found text for a nil-UUID compliance run'
      ).toBe(true);
    });
  });
});
