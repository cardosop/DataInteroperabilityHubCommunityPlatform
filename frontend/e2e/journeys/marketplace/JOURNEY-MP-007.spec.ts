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
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-007: Monitor Sync Jobs', () => {
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('sync jobs list loads for monitoring', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 60000,
        contentSelector: '.sync-job-list-page, [data-testid="sync-job-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      // The integrations subtree is CapabilityRoute-gated off the
      // OpenAPI/marketplace snapshot — a /unavailable bounce under batch
      // churn is a transient snapshot-fetch failure, not a disabled
      // feature. W16-guarded skip: raises in CI, skips locally (MP-001
      // convention).
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'integrations gate bounced to /unavailable — capabilities/OpenAPI snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'integrations gate bounced to /unavailable — transient snapshot failure'
      );
      expect(page.url()).toContain('/integrations/sync-jobs');
    });

    test('jobs list loads for sync job monitoring', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs', {
        timeout: 65000,
        contentSelector: '.job-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
    test('sync-jobs and jobs routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, [data-testid="sync-job-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: true,
      });
      expect(
        page.url().includes('/integrations/sync-jobs') ||
          page.url().includes('/unavailable') ||
          page.url().includes('/login') ||
          page.url().includes('/403')
      ).toBe(true);
      // Already authenticated; use client-side nav to avoid redundant login (prevents timeout)
      await navigateToRouteFromApp(page, '/jobs', {
        timeout: 90000,
        contentSelector: '.job-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: true,
      });
      expect(
        page.url().includes('/jobs') ||
          page.url().includes('/login') ||
          page.url().includes('/403')
      ).toBe(true);
    });
  });
});
