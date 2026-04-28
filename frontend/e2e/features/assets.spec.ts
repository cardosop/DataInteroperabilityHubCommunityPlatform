/**
 * E2E Feature: Assets
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /assets, /assets/create, /assets/:id.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Assets', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      await assertListPageLoads(page, '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"]', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('asset detail with non-existent id shows error or redirect', async ({ page }) => {
      const testUser = await getTestUser();
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await loginAndNavigateToRoute(page, testUser, `/assets/${nonExistentId}`, {
        timeout: 60000,
        contentSelector: '.error-display, [data-testid="error-display"], .asset-detail-page, [data-testid="asset-detail-page"], h1',
      });
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.asset-detail-content, .asset-detail-page, [data-testid="asset-detail-page"]',
      });
    });
  });

  test.describe('Edge', () => {
    test('assets create route loads or requires auth', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets/create', {
        timeout: 60000,
        contentSelector: 'form, .asset-form, .asset-create-page, [data-testid="asset-create-page"], h1',
      });
      const url = page.url();
      if (url.includes('/login')) {
        // Auth redirect — acceptable
        return;
      }
      // Must show a form — not just be on the URL
      const hasForm =
        (await page.locator('form').count()) > 0 ||
        (await page.locator('.asset-form, .asset-create-page, [data-testid="asset-create-page"]').count()) > 0;
      expect(
        hasForm,
        'Expected a form (.asset-form or <form>) to be present on /assets/create'
      ).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 3000 });
    });
  });
});
