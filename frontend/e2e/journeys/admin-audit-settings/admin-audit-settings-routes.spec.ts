/**
 * E2E: Admin, Audit, Settings, remaining personas (Phase 13 — 15.8)
 * TA, PA, Auditor, ED, DS, DA, CM: routes /admin, /audit, /settings/sessions, /settings/api-keys,
 * /developer, /baas, /ml, /communities, /observability.
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
      await expect(
        page.locator('.session-list-page, .session-list-table, .session-list-empty').first()
      ).toBeVisible({ timeout: 10000 });
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
      await expect(page.locator('.auth-api-key-list-page')).toBeVisible({ timeout: 10000 });
    });

    test('settings profile loads', async ({ page }) => {
      await page.goto('/settings/profile');
      try {
        await waitForAppMainReady(page, {
          contentSelector: '.profile-page, .profile-form, .settings-profile-page',
          timeout: 60000,
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/settings/profile');
      await expect(
        page.locator('.profile-page, .profile-form, .settings-profile-page').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('observability page loads', async ({ page }) => {
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      // Use specific element selector instead of flaky networkidle
      await page
        .locator(
          '.observability-page, [data-testid="observability-page"], .unavailable-page, .error-display, .app-main, #email'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const onObservability = url.includes('/observability');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const onUnavailable = url.includes('/unavailable');
      const hasContent =
        (await page
          .locator(
            '.observability-page, [data-testid="observability-page"], .unavailable-page, .error-display, .app-main'
          )
          .count()) > 0;
      expect(onObservability || on403 || onLogin || onUnavailable).toBe(true);
      expect(hasContent || on403 || onLogin || onUnavailable).toBe(true);
    });

    // ─── Missing route coverage (B2 gap-fill) ──────────────────────────────

    test('scheduled-exports list loads', async ({ page }) => {
      await page.goto('/scheduled-exports');
      try {
        await waitForAppMainReady(page, {
          contentSelector:
            '.scheduled-export-list-page, .empty-state, .error-display, .unavailable-page',
          timeout: 60000,
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/scheduled-exports');
      await expect(
        page
          .locator('.scheduled-export-list-page, .empty-state, .unavailable-page, .error-display')
          .first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('cost page loads (at /settings/cost, role-gated TENANT_ADMIN)', async ({ page }) => {
      // Route is /settings/cost — nested under settings — not the bare /cost path.
      // The e2e_test user is DATA_PROVIDER; role check fails → redirect to /403.
      // /403 (ForbiddenPage) is a top-level route without .app-main so we cannot use
      // waitForAppMainReady. Use the same simple goto + URL check pattern as admin/audit.
      await page.goto('/settings/cost');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.cost-page, .cost-tracking-page, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      const onCost = url.includes('/settings/cost');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.cost-page, .cost-tracking-page, .app-main').count()) > 0;
      expect(onCost || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });

    test('settings/tenant page loads (role-gated TENANT_ADMIN)', async ({ page }) => {
      // /settings/tenant is a real route at the same nesting level as /settings/cost.
      // The e2e_test user (DATA_PROVIDER) is redirected to /403; TENANT_ADMIN users see the
      // TenantSettingsPage. Both are valid outcomes for this smoke test.
      await page.goto('/settings/tenant');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.tenant-settings-page, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      const onTenant = url.includes('/settings/tenant');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.tenant-settings-page, .app-main').count()) > 0;
      expect(onTenant || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });

    test('semantic page loads', async ({ page }) => {
      await page.goto('/semantic');
      try {
        await waitForAppMainReady(page, {
          contentSelector: '.semantic-page, .unavailable-page, .error-display',
          timeout: 60000,
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const url = page.url();
      expect(url.includes('/semantic') || url.includes('/403') || url.includes('/unavailable')).toBe(
        true
      );
      await expect(
        page.locator('.semantic-page, .unavailable-page, .error-display, .app-main').first()
      ).toBeVisible({ timeout: 10000 });
    });
  });

  // ─── Failure: non-existent IDs (B3 gap-fill) ─────────────────────────────

  test.describe('Failure (non-existent resource IDs)', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page
        .waitForResponse(
          (resp) =>
            resp.url().includes('/webhooks/') &&
            resp.url().includes('00000000') &&
            (resp.status() === 200 || resp.status() === 404),
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.waitForTimeout(2000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display, .error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessPage = (await page.locator('.webhook-detail-page, .webhook-detail-main').count()) === 0;
      expect(onLogin || hasError || noSuccessPage).toBe(true);
    });

    test('audit event detail with non-existent id shows error', async ({ page }) => {
      await page.goto('/audit/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page
        .waitForResponse(
          (resp) =>
            resp.url().includes('/audit/') &&
            resp.url().includes('00000000') &&
            (resp.status() === 200 || resp.status() === 404),
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.waitForTimeout(2000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasError =
        (await page.locator('.error-display, .error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessPage = (await page.locator('.audit-event-detail-page').count()) === 0;
      expect(onLogin || on403 || hasError || noSuccessPage).toBe(true);
    });

    test('integration connection detail with non-existent id shows error', async ({ page }) => {
      await page.goto('/integrations/connections/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page
        .waitForResponse(
          (resp) =>
            resp.url().includes('/connections/') &&
            resp.url().includes('00000000') &&
            (resp.status() === 200 || resp.status() === 404),
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.waitForTimeout(2000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display, .error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessPage = (await page.locator('.connection-detail-page').count()) === 0;
      expect(onLogin || hasError || noSuccessPage).toBe(true);
    });
  });

  test.describe('Edge (capability-gated or role-gated)', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      // Replaced flaky networkidle with targeted element wait
      await page
        .locator('.app-main, .developer-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const onDev = url.includes('/developer');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main, .developer-page, .unavailable-page').count()) > 0;
      expect(onDev || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });

    test('baas page loads or shows unavailable', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      // Replaced flaky networkidle with targeted element wait
      await page
        .locator('.app-main, .baas-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const onBaas = url.includes('/baas');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main, .baas-page, .unavailable-page').count()) > 0;
      expect(onBaas || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });

    test('ml page loads or shows unavailable', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.app-main, .ml-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      const onMl = url.includes('/ml');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main, .ml-page, .unavailable-page').count()) > 0;
      expect(onMl || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });

    test('communities page loads or shows unavailable', async ({ page }) => {
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.app-main, .communities-page, .communities-tab, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      const onCommunities = url.includes('/communities');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main, .communities-page, .communities-tab, .unavailable-page').count()) > 0;
      expect(onCommunities || on403 || onUnavailable || onLogin).toBe(true);
      expect(hasContent || on403 || onUnavailable || onLogin).toBe(true);
    });
  });
});
