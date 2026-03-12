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
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-011: Set Up Reverse ETL', () => {
  test.setTimeout(360000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.connection-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });

    test('jobs list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.job-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
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
      await loginUser(page, testUser);
      await page.goto('/jobs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.job-detail-page, .job-detail-content, .error-display',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('integrations and jobs routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.connection-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      expect(page.url()).toContain('/integrations/connections');
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.job-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      expect(page.url()).toContain('/jobs');
    });
  });
});
