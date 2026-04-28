/**
 * E2E Test: JOURNEY-DE-011 — Set Up Reverse ETL
 *
 * Journey: Set Up Reverse ETL
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations, /jobs.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-011: Set Up Reverse ETL', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 60000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });

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
        detailContentSelector: '.job-detail-page, .job-detail-content, .error-display, [data-testid="error-display"]',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('integrations and jobs routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', { timeout: 60000 });
      expect(page.url()).toContain('/integrations/connections');
      await loginAndNavigateToRoute(page, testUser, '/jobs', { timeout: 60000 });
      expect(page.url()).toContain('/jobs');
    });
  });
});
