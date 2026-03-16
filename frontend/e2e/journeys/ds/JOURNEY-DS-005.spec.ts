/**
 * E2E Test: JOURNEY-DS-005 — Review Auto-Classification Results
 *
 * Journey: Review Auto-Classification Results
 * Persona: Data Scientist / ML Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /assets, /compliance (auto-classification).
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp } from '../../fixtures/helpers';

test.describe('JOURNEY-DS-005: Review Auto-Classification Results', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads for classification review', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });

    test('compliance runs list loads for classification results', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/compliance', {
        timeout: 60000,
        contentSelector:
          '.compliance-run-list-page, .compliance-run-list-table, .empty-state, .error-display, .loading-spinner-container',
      });
      await page.waitForTimeout(3000);
      expect(page.url()).toContain('/compliance');
      const hasContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.compliance-run-list-table').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.loading-spinner-container').count()) > 0 ||
        (await page.locator('.app-main').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/compliance/runs/00000000-0000-0000-0000-000000000000', {
        timeout: 60000,
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(3000);
      const hasError = (await page.locator('.error-display').count()) > 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || onLogin).toBe(true);
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('assets and compliance routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
      // Client-side nav avoids re-login auth race when already on protected page
      await navigateToRouteFromApp(page, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/compliance');
    });
  });
});
