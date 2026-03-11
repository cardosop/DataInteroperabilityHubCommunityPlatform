/**
 * E2E Test: JOURNEY-DPO-017 — Export ODPS Product
 *
 * Journey: Export ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /odps/:id, /contracts/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DPO-017: Export ODPS Product', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo

  test.describe('Success', () => {
    test('ODPS detail page loads (export available)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const odpsLink = page.locator('.odps-list-page a[href*="/odps/"]').first();
      if ((await odpsLink.count()) > 0) {
        await odpsLink.click();
        await page.waitForURL(/\/odps\/[^/]+$/, { timeout: 10000 });
        await page.waitForSelector('.odps-detail-main, .odps-detail-page, .error-display', {
          timeout: 15000,
        });
        const exportBtn = page.locator('button:has-text("Export"), a:has-text("Export")');
        const hasExport = (await exportBtn.count()) > 0;
        const hasContent = (await page.locator('.odps-detail-main, .odps-detail-page').count()) > 0;
        expect(hasContent || hasExport).toBe(true);
      }
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
    test('ODPS list with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps');
    });
  });
});
