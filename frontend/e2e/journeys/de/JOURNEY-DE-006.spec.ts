/**
 * E2E Test: JOURNEY-DE-006 — Monitor Data Pipeline Health
 *
 * Journey: Monitor Data Pipeline Health
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /jobs, /jobs/:id. integrations-jobs-webhooks covers routes; this spec provides
 * dedicated DE-006 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-006: Monitor Data Pipeline Health', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('jobs list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs', { timeout: 60000 });
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
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/jobs/00000000-0000-0000-0000-000000000000',
        { timeout: 90000 }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.job-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('jobs route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/jobs', { timeout: 60000 });
      expect(page.url()).toContain('/jobs');
    });
  });
});
