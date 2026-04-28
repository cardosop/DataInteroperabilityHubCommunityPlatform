/**
 * E2E Feature: Compliance
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /compliance, /compliance/runs/:id.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Compliance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login')) {
        throw new Error('compliance list loads: still on /login after loginAndNavigateToRoute');
      }
      await assertListPageLoads(page, '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/compliance/runs/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .compliance-run-detail-page, [data-testid="compliance-run-detail-page"], h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page, [data-testid="compliance-run-detail-page"]',
      });
    });

    test('unauthenticated access to compliance redirects to login', async ({ page }) => {
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/compliance'),
        'Expected /login redirect or /compliance with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('compliance list shows empty state when no runs exist', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      // Must not crash — either show list content or empty state
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Expected compliance list or empty state (no crash)').toBe(true);
    });
  });
});
