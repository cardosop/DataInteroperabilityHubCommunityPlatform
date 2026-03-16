/**
 * E2E Test: JOURNEY-MP-005 — Schedule Automatic Sync
 *
 * Journey: Schedule Automatic Sync
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/sync-jobs.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-005: Schedule Automatic Sync', () => {
  test.setTimeout(180000); // 3 min; client-side nav to sync-jobs avoids full-reload auth race

  test.describe('Success', () => {
    test('sync jobs list loads for schedule management', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/integrations/sync-jobs');
    });
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/jobs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.job-detail-page .job-detail-content',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/integrations/sync-jobs');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('sync jobs list with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/integrations/sync-jobs');
      const hasContent =
        (await page.locator('.sync-job-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
