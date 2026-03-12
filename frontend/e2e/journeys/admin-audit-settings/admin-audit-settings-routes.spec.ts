/**
 * E2E: Admin, Audit, Settings, remaining personas (Phase 13 — 15.8)
 * TA, PA, Auditor, ED, DS, DA, CM: routes /admin, /audit, /settings/sessions, /settings/api-keys,
 * /developer, /baas, /ml, /communities, /observability.
 * Role-gated routes: assert 403 or redirect when role missing. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import {
  assertCapabilityGatedPageLoads,
  assertListPageLoads,
  hasLoginPrompt,
  waitForAppMainReady,
} from '../../fixtures/helpers';

test.describe('Admin, Audit, Settings, remaining persona routes', () => {
  test.setTimeout(120000);

  test.describe('Failure', () => {
    test('unauthenticated access to admin route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      // We include /admin in waitForURL only as a timing backstop — not as a passing outcome.
      // After waitForURL resolves, only /login or /403 are acceptable redirect destinations.
      // If the URL still contains /admin, the auth guard must at minimum show an inline login
      // prompt; if it shows the real admin page without any auth challenge, the test fails.
      await page.waitForURL(/\/(login|403|admin)/, { timeout: 20_000 });
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        // Correct: unauthenticated user was redirected to a protected page
        return;
      }
      if (url.includes('/admin')) {
        // Admin page reached without redirect — must show an inline login prompt; otherwise
        // the route is unprotected, which is a security defect that must fail this test.
        const prompt = await hasLoginPrompt(page);
        expect(prompt).toBe(true);
        return;
      }
      // Unexpected URL — fail with context
      expect(url).toMatch(/\/(login|403|admin)/);
    });
  });

  test.describe('Success (authenticated user reaches page or gets 403/unavailable)', () => {
    test('admin page loads or shows 403/redirect', async ({ page }) => {
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');

      // 403 and login redirects are acceptable (role-gated)
      if (on403 || onLogin) return;

      expect(url).toContain('/admin');

      // .app-main alone is the generic app shell — it tells us nothing about page content.
      // error-display means something crashed — never acceptable as a success outcome.
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Admin page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(page.locator('.admin-page, .empty-state').first()).toBeVisible({ timeout: 10000 });
    });

    test('audit page loads or shows 403/redirect', async ({ page }) => {
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');

      if (on403 || onLogin) return;

      expect(url).toContain('/audit');

      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Audit page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(
        page.locator('.audit-event-list-page, .empty-state').first()
      ).toBeVisible({ timeout: 10000 });
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
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
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
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
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
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/settings/profile');
      await expect(
        page.locator('.profile-page, .profile-form, .settings-profile-page').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('observability page loads', async ({ page }) => {
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator(
          '.observability-page, [data-testid="observability-page"], .unavailable-page, .error-display, .app-main, #email'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');

      if (on403 || onLogin) return;

      // .app-main alone and error-display are never acceptable as success evidence
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Observability page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(
        page
          .locator('.observability-page, [data-testid="observability-page"], .unavailable-page')
          .first()
      ).toBeVisible({ timeout: 10000 });
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
      // .error-display must NOT appear in the final toBeVisible assertion — it was previously
      // included, causing broken pages to be silently accepted as passing.
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Scheduled-exports page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(
        page.locator('.scheduled-export-list-page, .empty-state, .unavailable-page').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('cost page loads (at /settings/cost, role-gated TENANT_ADMIN)', async ({ page }) => {
      // Route is /settings/cost — nested under settings.
      // The e2e_test user is DATA_PROVIDER; role check fails → redirect to /403.
      // /403 (ForbiddenPage) is a top-level route without .app-main.
      await page.goto('/settings/cost');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.cost-page, .cost-tracking-page, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');

      if (on403 || onLogin) return;

      // .app-main alone and error-display are never acceptable
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Cost page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(
        page.locator('.cost-page, .cost-tracking-page, .unavailable-page').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('settings/tenant page loads (role-gated TENANT_ADMIN)', async ({ page }) => {
      // /settings/tenant — TENANT_ADMIN sees TenantSettingsPage; DATA_PROVIDER gets /403.
      await page.goto('/settings/tenant');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.tenant-settings-page, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');

      if (on403 || onLogin) return;

      // .app-main alone is not acceptable
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Settings/tenant page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(
        page.locator('.tenant-settings-page, .unavailable-page').first()
      ).toBeVisible({ timeout: 10000 });
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
      if (url.includes('/403')) return;
      // .error-display and .app-main are never acceptable in the final assertion
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Semantic page shows error state: "${errText?.slice(0, 300)}"`);
      }
      await expect(
        page.locator('.semantic-page, .unavailable-page').first()
      ).toBeVisible({ timeout: 10000 });
    });
  });

  // ─── Failure: non-existent IDs (B3 gap-fill) ─────────────────────────────

  test.describe('Failure (non-existent resource IDs)', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Fixed: use full path instead of partial `/webhooks/` && `00000000` (too broad).
      // Only 404 is valid; 200 means the webhook exists (backend bug).
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/webhooks/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/webhooks/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .webhook-detail-page')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Webhook detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });

    test('audit event detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Fixed: use full path instead of partial `/audit/` && `00000000` (too broad).
      // Audit is role-gated (AUDITOR/TENANT_ADMIN) — 403 is also an acceptable outcome.
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/audit/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/audit/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, [data-testid="audit-event-detail-page"]')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      if (onLogin || on403) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Audit event detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });

    test('integration connection detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Fixed: use full path including /integrations/ prefix instead of just /connections/.
      // The previous pattern `includes('/connections/')` would match ANY connection request,
      // not specifically the integrations connection detail for the nil UUID.
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/integrations/connections/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/integrations/connections/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .marketplace-connection-detail-page')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Integration connection detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });
  });

  test.describe('Edge (capability-gated or role-gated)', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      // DeveloperPortalPage renders .developer-portal-page (not .developer-page)
      await page
        .locator('.developer-portal-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) return;
      // Valid: .developer-portal-page (DeveloperPortalPage.tsx:36) OR .unavailable-page (capability disabled).
      // .app-main alone and error-display are never acceptable.
      await assertCapabilityGatedPageLoads(page, '.developer-portal-page, .unavailable-page');
    });

    test('baas page loads or shows unavailable', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.baas-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) return;
      await assertCapabilityGatedPageLoads(page, '.baas-page, .unavailable-page');
    });

    test('ml page loads or shows unavailable', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.ml-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) return;
      await assertCapabilityGatedPageLoads(page, '.ml-page, .unavailable-page');
    });

    test('communities page loads or shows unavailable', async ({ page }) => {
      await page.goto('/communities');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.communities-page, .communities-tab, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) return;
      await assertCapabilityGatedPageLoads(page, '.communities-page, .communities-tab, .unavailable-page');
    });
  });
});
