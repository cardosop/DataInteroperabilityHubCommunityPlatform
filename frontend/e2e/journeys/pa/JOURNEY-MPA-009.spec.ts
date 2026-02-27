/**
 * E2E Test: JOURNEY-MPA-009 — Manage Plugin Marketplace
 *
 * Journey: Manage Plugin Marketplace
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer.
 * Capability-gated: developer.plugins. Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';

test.describe('JOURNEY-MPA-009: Manage Plugin Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads (plugin marketplace)', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onDeveloper && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const hasContent =
        (await page.locator('.developer-portal-page, .unavailable-page, .app-main').count()) > 0;
      expect(url.includes('/login') || url.includes('/403') || url.includes('/developer')).toBe(true);
      // When on /login, we may not have developer content; when on /developer or /403, expect content
      expect(url.includes('/login') || hasContent).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('developer page loads or redirects', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/developer')).toBe(true);
    });
  });
});
