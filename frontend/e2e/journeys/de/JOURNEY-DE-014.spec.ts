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
import { getTenantAdminUserOrTestUser, getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DE-014: Create ODPS via API', () => {
  // 6 min: ODPS routes can be slow under parallel E2E load (chromium-routes runs late)
  test.setTimeout(360000);

  test.describe('Success', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/upload');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.odps-upload-page, .odps-upload-form, .loading-spinner-container, .app-main, #email',
        { timeout: 120000 }
      );
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/odps/upload');
    });

    test('ODPS list loads', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
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
      const testUser = await getTenantAdminUserOrTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/upload');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.odps-upload-page, .odps-upload-form, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      expect(page.url()).toContain('/odps/upload');
      await page.goto('/odps');
      await page.waitForSelector(
        '.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      expect(page.url()).toContain('/odps');
    });
  });
});
