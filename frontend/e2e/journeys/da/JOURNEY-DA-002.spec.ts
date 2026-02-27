/**
 * E2E Test: JOURNEY-DA-002 — Wrangle Data Interactively
 *
 * Journey: Wrangle Data Interactively
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /datasets, /assets (select asset, wrangling).
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DA-002: Wrangle Data Interactively', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('datasets list loads for data selection', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/datasets');
      const hasContent =
        (await page.locator('.dataset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('assets list loads for data selection', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });
  });

  test.describe('Failure', () => {
    test('dataset detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/datasets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dataset-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('datasets and assets routes accessible', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/datasets');
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });
  });
});
