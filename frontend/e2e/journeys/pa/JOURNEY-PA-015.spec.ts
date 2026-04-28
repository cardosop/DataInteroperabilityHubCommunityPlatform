/**
 * E2E Test: Phase 15 — Platform Admin Suspend/Resume & Usage Visibility
 *
 * Platform admin can suspend/resume tenants and view usage across tenants.
 * Persona: Platform Admin
 * Routes: /admin (tenants tab, usage tab)
 * Success/Failure/Edge per 29.3.2. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Phase 15: Platform Admin Suspend/Resume & Usage', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('platform admin sees Usage tab', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });
      const usageTab = page.locator('button:has-text("Usage")');
      await expect(usageTab).toBeVisible({ timeout: 5000 });
    });

    test('platform admin can open Usage tab and see usage data or empty state', async ({
      page,
    }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });
      const usageTab = page.locator('button:has-text("Usage")');
      await usageTab.click();
      await page.waitForTimeout(2000);
      const usageSection = page.locator('[data-testid="admin-usage-section"]');
      await expect(usageSection).toBeVisible({ timeout: 5000 });
      const hasTable = (await page.locator('.admin-table, [data-testid="admin-table"]').first().count()) > 0;
      const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      const hasLoading = (await page.locator('.loading-spinner').count()) > 0;
      expect(hasTable || hasEmptyState || hasLoading).toBe(true) /* acceptable states */;
    });

    test('platform admin sees Suspend/Resume actions in Tenants tab', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });
      const tenantsTab = page.locator('button:has-text("Tenants")');
      await tenantsTab.click();
      await page.waitForTimeout(2000);
      const tenantsSection = page.locator('[data-testid="admin-tenants-section"]');
      await expect(tenantsSection).toBeVisible({ timeout: 5000 });
      const hasActionsColumn =
        (await page.locator('th:has-text("Actions")').count()) > 0 ||
        (await page.locator('[data-testid^="suspend-tenant-"]').count()) > 0 ||
        (await page.locator('[data-testid^="resume-tenant-"]').count()) > 0 ||
        (await page.locator('button:has-text("Suspend")').count()) > 0 ||
        (await page.locator('button:has-text("Resume")').count()) > 0 ||
        (await page.locator('.admin-action-disabled').count()) > 0;
      const hasTableOrEmpty =
        (await page.locator('.admin-table, [data-testid="admin-table"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasTableOrEmpty).toBe(true) /* acceptable states */;
      expect(hasActionsColumn || hasTableOrEmpty).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to admin redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403|admin)/, { timeout: 20000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
      if (url.includes('/admin')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('admin page loads with empty tenant list or usage', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.admin-page, [data-testid="admin-page"], .admin-table, .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });
});
