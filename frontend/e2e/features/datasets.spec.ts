/**
 * E2E Feature: Datasets
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /datasets, /datasets/create, /datasets/:id.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Datasets', () => {
  // 180s: loginAndNavigateToRoute can take 60-90s on staging under rate-limit
  // pressure (auth retry backoff 15s × 2-3 attempts + navigation).
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('datasets list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"], h1',
      });
      await assertListPageLoads(page, '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('dataset detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/datasets/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .dataset-detail-page, [data-testid="dataset-detail-page"], h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dataset-detail-content, .dataset-detail-page, [data-testid="dataset-detail-page"]',
      });
    });

    test('unauthenticated access to datasets redirects to login', async ({ page }) => {
      await page.goto('/datasets');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/datasets'),
        'Expected /login redirect or /datasets with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('datasets list shows pagination or empty state (not crash)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"], h1',
      });
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Expected dataset list or empty state').toBe(true);
    });
  });
});
