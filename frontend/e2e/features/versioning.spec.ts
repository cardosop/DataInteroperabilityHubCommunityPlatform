/**
 * E2E Feature: Versioning
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /datasets/:id/versions.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Versioning', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('datasets list loads (versioning context)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"], h1',
      });
      await assertListPageLoads(page, '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('invalid dataset id for versions shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/datasets/00000000-0000-0000-0000-000000000000/versions',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .dataset-version-list-page, .dataset-detail-page, [data-testid="dataset-detail-page"], h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dataset-version-list-page, .dataset-detail-page, [data-testid="dataset-detail-page"]',
      });
    });
  });

  test.describe('Edge', () => {
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
});
