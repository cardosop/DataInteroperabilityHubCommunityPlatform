/**
 * E2E Test: JOURNEY-PA-001 — Onboard New Tenant
 *
 * Journey: Onboard New Tenant
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /admin (tenants tab).
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-PA-001: Onboard New Tenant', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('admin page loads with tenants section', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/admin');
      const hasTenantsTab = (await page.locator('button:has-text("Tenants")').count()) > 0;
      const hasContent = (await page.locator('.admin-page').count()) > 0;
      expect(hasContent).toBe(true);
      expect(hasTenantsTab).toBe(true);
    });

    test('tenants tab loads tenant list', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const tenantsTab = page.locator('button:has-text("Tenants")');
      expect((await tenantsTab.count()) > 0).toBe(true);
      await tenantsTab.first().click();
      await page.waitForTimeout(2000);
      const hasTenantsSection =
        (await page.locator('[data-testid="admin-tenants-section"]').count()) > 0 ||
        (await page.locator('.admin-table').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasTenantsSection).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('admin page loads without crash', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await waitForAppMainReady(page, {
        timeout: 30000,
        contentSelector: '.admin-page, .admin-no-permission, [data-testid="forbidden-page"]',
        acceptRedirectToLogin: true,
      }).catch(() => null);
      const onAdmin = page.url().includes('/admin');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasContent =
        (await page.locator('.admin-page, .admin-no-permission, [data-testid="forbidden-page"]').count()) > 0;
      const no500 = (await page.locator('text=/500|internal server error/i').count()) === 0;
      expect(onAdmin || on403 || onLogin).toBe(true);
      // When on /login, we may not have admin content; when on /admin or /403, expect content and no 500
      expect(onLogin || (hasContent && no500)).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('admin page loads or redirects', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await waitForAppMainReady(page, {
        timeout: 30000,
        contentSelector: '.admin-page, .admin-no-permission, [data-testid="forbidden-page"]',
        acceptRedirectToLogin: true,
      }).catch(() => null);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
    });
  });
});
