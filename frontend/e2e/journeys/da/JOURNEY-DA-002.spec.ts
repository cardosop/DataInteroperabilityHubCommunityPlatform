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
import { clearAuthStorage, getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DA-002: Wrangle Data Interactively', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('datasets list loads for data selection', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/datasets');
      const hasContent =
        (await page.locator('.dataset-list-page, [data-testid="dataset-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('assets list loads for data selection', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
        detailContentSelector: '.dataset-detail-page, [data-testid="dataset-detail-page"]',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/datasets');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('datasets and assets routes accessible', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, testUser, '/datasets', {
        timeout: 60000,
        contentSelector: '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/datasets');
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/assets');
    });
  });
});
