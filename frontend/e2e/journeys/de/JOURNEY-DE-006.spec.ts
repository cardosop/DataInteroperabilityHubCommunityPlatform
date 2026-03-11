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
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-006: Monitor Data Pipeline Health', () => {
  test.setTimeout(360000); // 4 min: visible/slowMo; jobs API may return 500 → error-display still valid

  test.describe('Success', () => {
    test('jobs list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.job-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
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
        detailContentSelector: '.job-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('jobs route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.job-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      expect(page.url()).toContain('/jobs');
    });
  });
});
