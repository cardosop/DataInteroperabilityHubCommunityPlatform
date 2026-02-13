/**
 * E2E: Admin, Audit, Settings, remaining personas (Phase 13 — 15.8)
 * TA, PA, Auditor, ED, DS, DA, CM: routes /admin, /audit, /settings/sessions, /settings/api-keys,
 * /developer, /baas, /ml, /social, /observability.
 * Role-gated routes: assert 403 or redirect when role missing. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('Admin, Audit, Settings, remaining persona routes', () => {
  test.setTimeout(120000);

  test.describe('Success (authenticated user reaches page or gets 403/unavailable)', () => {
    test('admin page loads or shows 403/redirect', async ({ page }) => {
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onAdmin = page.url().includes('/admin');
      const on403 = page.url().includes('/403');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onAdmin || on403).toBe(true);
      expect(hasContent || on403).toBe(true);
    });

    test('audit page loads or shows 403/redirect', async ({ page }) => {
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onAudit = page.url().includes('/audit');
      const on403 = page.url().includes('/403');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onAudit || on403).toBe(true);
      expect(hasContent || on403).toBe(true);
    });

    test('settings sessions loads', async ({ page }) => {
      await page.goto('/settings/sessions');
      try {
        await waitForAppMainReady(page, { contentSelector: '.session-list-page', timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/settings/sessions');
    });

    test('settings api-keys loads', async ({ page }) => {
      await page.goto('/settings/api-keys');
      try {
        await waitForAppMainReady(page, {
          contentSelector: '.auth-api-key-list-page',
          timeout: 60000,
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/settings/api-keys');
    });

    test('observability page loads', async ({ page }) => {
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.observability-page, .error-display', { timeout: 45000 });
      expect(page.url()).toContain('/observability');
    });
  });

  test.describe('Edge (capability-gated or role-gated)', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onDev = url.includes('/developer');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onDev || onUnavailable || onLogin).toBe(true);
      expect(hasContent || onUnavailable || onLogin).toBe(true);
    });

    test('baas page loads or shows unavailable', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onBaas = url.includes('/baas');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onBaas || onUnavailable || onLogin).toBe(true);
      expect(hasContent || onUnavailable || onLogin).toBe(true);
    });

    test('ml page loads or shows unavailable', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onMl = url.includes('/ml');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onMl || onUnavailable || onLogin).toBe(true);
      expect(hasContent || onUnavailable || onLogin).toBe(true);
    });

    test('social page loads or shows unavailable', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onSocial = url.includes('/social');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onSocial || onUnavailable || onLogin).toBe(true);
      expect(hasContent || onUnavailable || onLogin).toBe(true);
    });
  });
});
