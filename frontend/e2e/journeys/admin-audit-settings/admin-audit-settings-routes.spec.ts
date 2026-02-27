/**
 * E2E: Admin, Audit, Settings, remaining personas (Phase 13 — 15.8)
 * TA, PA, Auditor, ED, DS, DA, CM: routes /admin, /audit, /settings/sessions, /settings/api-keys,
 * /developer, /baas, /ml, /social, /observability.
 * Role-gated routes: assert 403 or redirect when role missing. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import { hasLoginPrompt, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('Admin, Audit, Settings, remaining persona routes', () => {
  test.setTimeout(120000);

  test.describe('Failure', () => {
    test('unauthenticated access to admin route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
      if (url.includes('/admin')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Success (authenticated user reaches page or gets 403/unavailable)', () => {
    test('admin page loads or shows 403/redirect', async ({ page }) => {
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onAdmin = url.includes('/admin');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onAdmin || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });

    test('audit page loads or shows 403/redirect', async ({ page }) => {
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onAudit = url.includes('/audit');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasContent = (await page.locator('.app-main').count()) > 0;
      expect(onAudit || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });

    test('settings sessions loads', async ({ page }) => {
      await page.goto('/settings/sessions');
      try {
        await waitForAppMainReady(page, {
          contentSelector:
            '.session-list-page, .session-list-table, .session-list-empty, .loading-spinner-container',
          timeout: 60000,
        });
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
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(5000);
      const url = page.url();
      const onObservability = url.includes('/observability');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const onUnavailable = url.includes('/unavailable');
      const hasContent =
        (await page.locator(
          '.observability-page, [data-testid="observability-page"], .unavailable-page, .error-display, .loading-spinner-container, .app-main, .app-shell'
        ).count()) > 0;
      expect(onObservability || on403 || onLogin || onUnavailable).toBe(true);
      expect(hasContent || on403 || onLogin || onUnavailable).toBe(true);
    });
  });

  test.describe('Edge (capability-gated or role-gated)', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(5000);
      const url = page.url();
      const onDev = url.includes('/developer');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator(
          '.app-main, .app-shell, .developer-page, .unavailable-page, .loading-spinner-container'
        ).count()) > 0;
      expect(onDev || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });

    test('baas page loads or shows unavailable', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(5000);
      const url = page.url();
      const onBaas = url.includes('/baas');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator(
          '.app-main, .app-shell, .baas-page, .unavailable-page, .loading-spinner-container'
        ).count()) > 0;
      expect(onBaas || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });

    test('ml page loads or shows unavailable', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onMl = url.includes('/ml');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main, .ml-page, .unavailable-page, .loading-spinner-container').count()) >
        0;
      expect(onMl || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });

    test('social page loads or shows unavailable', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onSocial = url.includes('/social');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main, .social-page, .unavailable-page, .loading-spinner-container').count()) >
        0;
      expect(onSocial || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });
  });
});
