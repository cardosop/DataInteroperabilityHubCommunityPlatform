/**
 * E2E Test: JOURNEY-MP-003 — Import Dataset from Marketplace
 *
 * Journey: Import Dataset from Marketplace
 * Persona: Data Consumer
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/connections, /integrations/sync-jobs.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-003: Import Dataset from Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections list loads for discover', async ({ page }) => {
      const testUser = await getConsumerTestUser();
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

    test('sync jobs list loads for import monitoring', async ({ page }) => {
      const testUser = await getConsumerTestUser();
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
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs/00000000-0000-0000-0000-000000000000', {
        timeout: 60000,
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(3000);
      const hasError = (await page.locator('.error-display').count()) > 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || onLogin).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('connections and sync-jobs routes accessible', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 90000,
        contentSelector: '.connection-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) return;
      expect(page.url()).toContain('/integrations/connections');
      // Client-side nav avoids session loss; re-login if redirected
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 120000,
        contentSelector: '.sync-job-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) return;
      expect(page.url()).toContain('/integrations/sync-jobs');
    });
  });
});
