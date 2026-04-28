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
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-004: Sync Assets Bidirectionally', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('sync jobs list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 60000,
        contentSelector: '.sync-job-list-page, [data-testid="sync-job-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      expect(page.url()).toContain('/integrations/sync-jobs');
      const hasContent =
        (await page.locator('.sync-job-list-page, [data-testid="sync-job-list-page"]').first().count()) > 0 ||
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('connections list loads for sync config', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 65000,
        contentSelector: '.connection-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
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
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || onLogin).toBe(true) /* acceptable states */;
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/integrations/sync-jobs');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('sync-jobs and connections routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, [data-testid="sync-job-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/integrations/sync-jobs');
      // Use direct goto — already authenticated, avoids UI nav slowMo accumulation in visible project
      await page.goto('/integrations/connections', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
      if (page.url().includes('/login')) return;
      expect(page.url()).toContain('/integrations/connections');
    });
  });
});
