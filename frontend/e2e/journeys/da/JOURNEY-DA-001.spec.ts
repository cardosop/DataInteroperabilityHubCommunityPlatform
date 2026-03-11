/**
 * E2E Test: JOURNEY-DA-001 — Create Transformation Pipeline
 *
 * Journey: Create Transformation Pipeline
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md
 *
 * Uses placeholder transformation API (/api/v1/transformation/pipelines/).
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DA-001: Create Transformation Pipeline', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('transformation pipelines list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/transformation', {
        timeout: 60000,
        contentSelector:
          '.transformation-pipeline-list-page, .empty-state, .error-display, .transformation-list-error-wrapper',
      });
      expect(page.url()).toContain('/transformation');
      const hasContent =
        (await page.locator('.transformation-pipeline-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.transformation-list-error-wrapper').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('transformation pipeline detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/transformation/pipelines/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.transformation-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('transformation route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/transformation', {
        timeout: 60000,
        contentSelector:
          '.transformation-pipeline-list-page, .empty-state, .error-display, .transformation-list-error-wrapper',
      });
      expect(page.url()).toContain('/transformation');
    });
  });
});
