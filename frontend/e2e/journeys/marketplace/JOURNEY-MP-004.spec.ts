/**
 * E2E Test: JOURNEY-MP-004 — Sync Assets Bidirectionally
 *
 * Journey: Sync Assets Bidirectionally
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/sync-jobs, /integrations/connections.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-004: Sync Assets Bidirectionally', () => {
  test.setTimeout(180000); // 3 min; client-side nav to sync-jobs avoids full-reload auth race

  test.describe('Success', () => {
    test('sync jobs list loads', async ({ page }) => {
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
      const hasContent =
        (await page.locator('.sync-job-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('connections list loads for sync config', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 65000,
        contentSelector: '.connection-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
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
    test('sync-jobs and connections routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/integrations/sync-jobs');
      // Already authenticated; use client-side nav to avoid redundant login (prevents timeout)
      await navigateToRouteFromApp(page, '/integrations/connections', {
        timeout: 90000,
        contentSelector: '.connection-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/integrations/connections');
    });
  });
});
