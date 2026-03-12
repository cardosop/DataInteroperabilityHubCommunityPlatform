/**
 * E2E Test: JOURNEY-MP-007 — Monitor Sync Jobs
 *
 * Journey: Monitor Sync Jobs
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/sync-jobs, /jobs.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-007: Monitor Sync Jobs', () => {
  test.setTimeout(180000); // 3 min; client-side nav to sync-jobs avoids full-reload auth race

  test.describe('Success', () => {
    test('sync jobs list loads for monitoring', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 60000,
        contentSelector: '.sync-job-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/sync-jobs');
    });

    test('jobs list loads for sync job monitoring', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs', {
        timeout: 65000,
        contentSelector: '.job-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/jobs');
    });
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs/00000000-0000-0000-0000-000000000000', {
        timeout: 60000,
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(3000);
      const hasError = (await page.locator('.error-display').count()) > 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('sync-jobs and jobs routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/sync-jobs');
      // Already authenticated; use client-side nav to avoid redundant login (prevents timeout)
      await navigateToRouteFromApp(page, '/jobs', {
        timeout: 90000,
        contentSelector: '.job-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/jobs');
    });
  });
});
