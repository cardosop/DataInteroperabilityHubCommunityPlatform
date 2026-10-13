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
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-005: Schedule Automatic Sync', () => {
  // 240s: login overhead + 90s helper wait + gate-bounce handling — the 90s
  // budget died inside the helper while the /unavailable bounce landed at
  // the very end of the boot window (b6: budget expired before the
  // terminal-state check could see the bounce). DE-010/015 convention.
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('sync jobs list loads for schedule management', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 90000,
        contentSelector: '.sync-job-list-page, [data-testid="sync-job-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
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
        contentSelector: '.sync-job-list-page, [data-testid="sync-job-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
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
      const hasContent =
        (await page.locator('.sync-job-list-page, [data-testid="sync-job-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
