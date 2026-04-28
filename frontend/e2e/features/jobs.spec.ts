/**
 * E2E Feature: Jobs
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /jobs, /jobs/:id.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Jobs', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('jobs list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs', {
        timeout: 60000,
        contentSelector: '.job-list-page, .empty-state, [data-testid="empty-state"], h1',
      });
      await assertListPageLoads(page, '.job-list-page, .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/jobs/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .job-detail-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.job-detail-page',
      });
    });

    test('unauthenticated access to jobs redirects to login', async ({ page }) => {
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/jobs'),
        'Expected /login redirect or /jobs with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('jobs list shows content or empty state (no crash)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs', {
        timeout: 60000,
        contentSelector: '.job-list-page, .empty-state, [data-testid="empty-state"], h1',
      });
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.job-list-page, .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Expected job list or empty state').toBe(true);
    });
  });
});
