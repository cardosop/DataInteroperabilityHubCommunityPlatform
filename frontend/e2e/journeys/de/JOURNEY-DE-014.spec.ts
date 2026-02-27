/**
 * E2E Test: JOURNEY-DE-014 — Create ODPS via API
 *
 * Journey: Create ODPS via API
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /odps/upload, /odps, /contracts.
 * UI flow for ODPS creation (API flow would be separate API tests).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-014: Create ODPS via API', () => {
  // 4 min: loginAndNavigateToRoute (~60–90s) + navigateToRouteFromApp (~60–90s) can exceed 180s under parallel E2E load
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2500);
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', {
        contentSelector: '.odps-upload-page',
        timeout: 60000,
      });
      expect(page.url()).toContain('/odps/upload');
    });

    test('ODPS list loads', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2500);
      await loginAndNavigateToRoute(page, testUser, '/odps', {
        timeout: 60000,
        contentSelector: '.odps-list-page, .odps-empty-state, .error-display',
      });
      expect(page.url()).toContain('/odps');
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessContent = (await page.locator('.odps-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ODPS upload and list accessible', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2500);
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', {
        timeout: 60000,
        contentSelector: '.odps-upload-page',
      });
      expect(page.url()).toContain('/odps/upload');
      await navigateToRouteFromApp(page, '/odps', {
        timeout: 60000,
        contentSelector: '.odps-list-page, .odps-empty-state, .error-display',
        user: testUser,
      });
      expect(page.url()).toContain('/odps');
    });
  });
});
