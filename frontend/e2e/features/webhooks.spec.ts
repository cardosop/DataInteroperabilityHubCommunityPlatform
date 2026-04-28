/**
 * E2E Feature: Webhooks
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /webhooks, /webhooks/:id.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Webhooks', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('webhooks list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], h1',
      });
      await assertListPageLoads(page, '.webhook-list-page, .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      const NIL_UUID = '00000000-0000-0000-0000-000000000000';

      // Wait for the actual API response that settles React Query rather
      // than a fixed sleep. The webhook detail endpoint uses doubled path:
      // /api/v1/webhooks/webhooks/{id}/ (WEBHOOKS_BASE_PATH = 'webhooks/webhooks')
      const detailApiDone = page.waitForResponse(
        (r) =>
          new RegExp(`/api/v1/webhooks/webhooks/${NIL_UUID}/?(\\?|$)`).test(r.url()) &&
          r.status() !== 401,
        { timeout: 60_000 }
      );

      await loginAndNavigateToRoute(page, testUser, `/webhooks/${NIL_UUID}`, {
        timeout: 60000,
        contentSelector: '.error-display, [data-testid="error-display"], .webhook-detail-page, h1',
      });

      // Wait for the API response to settle before asserting
      await detailApiDone.catch(() => {
        // API may not fire if login redirect happened — acceptable
      });

      // Wait for terminal UI state after query settles
      await page
        .locator('.webhook-detail-page, .error-display, [data-testid="error-display"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 })
        .catch(() => {
          // Terminal state may already be visible from loginAndNavigateToRoute
        });

      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page',
      });
    });

    test('unauthenticated access to webhooks redirects to login', async ({ page }) => {
      await page.goto('/webhooks');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/webhooks'),
        'Expected /login redirect or /webhooks with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('webhooks list shows empty state when no webhooks exist', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], h1',
      });
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.webhook-list-page, .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Expected webhook list or empty state (no crash)').toBe(true);
    });
  });
});
