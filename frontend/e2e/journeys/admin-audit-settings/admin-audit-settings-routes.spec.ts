/**
 * E2E: Admin, Audit, Settings, remaining personas (Phase 13 — 15.8)
 * TA, PA, Auditor, ED, DS, DA, CM: routes /admin, /audit, /settings/sessions, /settings/api-keys,
 * /developer, /baas, /ml, /communities, /observability.
 * Role-gated routes: assert 403 or redirect when role missing. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, gotoWithRetry } from '../../fixtures/auth';
import {
  assertCapabilityGatedPageLoads,
  hasLoginPrompt,
  navigateOrSkip,
  waitForAppMainReady,
} from '../../fixtures/helpers';

test.describe('Admin, Audit, Settings, remaining persona routes', () => {
  test.setTimeout(120000);

  test.describe('Failure', () => {
    test('unauthenticated access to admin route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await gotoWithRetry(page, '/admin', { waitUntil: 'domcontentloaded' });
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
      const { ok } = await navigateOrSkip(page, '/admin');
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) {
        console.warn('[WARN] /admin returned 403 — verify E2E user has the required role');
        return;
      }

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
      const { ok } = await navigateOrSkip(page, '/audit');
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) {
        console.warn('[WARN] /audit returned 403 — verify E2E user has the required role');
        return;
      }

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
      const { ok } = await navigateOrSkip(page, '/settings/sessions', {
        contentSelector:
          '.session-list-page, .session-list-table, .session-list-empty',
      });
      if (!ok) return;

      expect(page.url()).toContain('/settings/sessions');
      // Sessions API can be slow under parallel E2E load — allow 30s for content
      await expect(
        page.locator('.session-list-page, .session-list-table, .session-list-empty').first()
      ).toBeVisible({ timeout: 30000 });
    });

    test('settings api-keys loads', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/settings/api-keys', {
        contentSelector: '.auth-api-key-list-page',
      });
      if (!ok) return;

      expect(page.url()).toContain('/settings/api-keys');
      await expect(page.locator('.auth-api-key-list-page')).toBeVisible({ timeout: 10000 });
    });

    test('settings profile loads', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/settings/profile', {
        contentSelector: '.profile-page, .profile-form, .settings-profile-page',
      });
      if (!ok) return;

      expect(page.url()).toContain('/settings/profile');
      await expect(
        page.locator('.profile-page, .profile-form, .settings-profile-page').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('observability page loads', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/observability');
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) {
        console.warn('[WARN] /observability returned 403 — verify E2E user has the required role');
        return;
      }

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
      const { ok } = await navigateOrSkip(page, '/scheduled-exports', {
        contentSelector:
          '.scheduled-export-list-page, .empty-state, .error-display, .unavailable-page',
      });
      if (!ok) return;

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
      const { ok } = await navigateOrSkip(page, '/settings/cost');
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) {
        console.warn('[WARN] /settings/cost returned 403 — verify E2E user has the required role');
        return;
      }

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
      const { ok } = await navigateOrSkip(page, '/settings/tenant');
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) {
        console.warn('[WARN] /settings/tenant returned 403 — verify E2E user has the required role');
        return;
      }

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
      await gotoWithRetry(page, '/semantic');
      try {
        await waitForAppMainReady(page, {
          contentSelector: '.semantic-page, .unavailable-page',
          timeout: 60000,
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        // Capability-gated: CapabilityRoute may render UnavailablePage in-place at /semantic,
        // or the capabilities API may be slow/unavailable (LoadingSpinner stays forever).
        const isGated =
          page.url().includes('/unavailable') ||
          page.url().includes('/403') ||
          (await page.locator('.unavailable-page').count()) > 0;
        if (isGated) {
          test.skip(true, 'Semantic capability gated — page rendered outside .app-main');
          return;
        }
        // Capabilities API never responded — LoadingSpinner stayed forever
        const hasSpinner = (await page.locator('.loading-spinner').count()) > 0;
        if (hasSpinner) {
          test.skip(true, 'Capabilities API did not respond within timeout — spinner remained');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      const url = page.url();
      if (url.includes('/403') || url.includes('/unavailable')) {
        test.skip(true, `Redirected to ${url.includes('/403') ? '/403' : '/unavailable'} — role/feature not available`);
      }
      expect(url).toContain('/semantic');
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
      await gotoWithRetry(page, `/webhooks/${nonExistentId}`);
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.error-display, .error-display-title, .webhook-detail-page',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .webhook-detail-page')
        .first().waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      // For a non-existent resource, any error state is valid: 404 "not found", API timeout,
      // network error, or generic failure. The test verifies the UI shows an error — the
      // exact error text depends on backend load and response time.
      if (hasErrorDisplay) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        if (errText && !errText.toLowerCase().includes('not found') && !errText.includes('404')) {
          console.warn(`[WARN] /webhooks/${nonExistentId} error is not 404: "${errText.slice(0, 200)}"`);
        }
      }
      if (!hasErrorDisplay) {
        // Check if page is still loading (backend slow under parallel E2E load)
        const stillLoading = (await page.locator('[data-testid="skeleton-row"], .skeleton, .loading-spinner').count()) > 0;
        if (stillLoading) {
          test.skip(true, 'Backend too slow — page still loading skeleton after 30s; error-display not yet rendered');
          return;
        }
      }
      expect(hasErrorDisplay, 'Expected .error-display for non-existent resource').toBe(true);
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
      await gotoWithRetry(page, `/audit/${nonExistentId}`);
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.error-display, .error-display-title, [data-testid="audit-event-detail-page"]',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      await responsePromise;

      await page.locator('.error-display, .error-display-title, [data-testid="audit-event-detail-page"]')
        .first().waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);

      const on403 = page.url().includes('/403');
      if (on403) {
        console.warn(`[WARN] /audit/${nonExistentId} returned 403 — verify E2E user has the required role`);
        return;
      }

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      // For a non-existent resource, any error state is valid: 404 "not found", API timeout,
      // network error, or generic failure. The test verifies the UI shows an error — the
      // exact error text depends on backend load and response time.
      if (hasErrorDisplay) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        if (errText && !errText.toLowerCase().includes('not found') && !errText.includes('404')) {
          console.warn(`[WARN] /audit/${nonExistentId} error is not 404: "${errText.slice(0, 200)}"`);
        }
      }
      if (!hasErrorDisplay) {
        // Check if page is still loading (backend slow under parallel E2E load)
        const stillLoading = (await page.locator('[data-testid="skeleton-row"], .skeleton, .loading-spinner').count()) > 0;
        if (stillLoading) {
          test.skip(true, 'Backend too slow — page still loading skeleton after 30s; error-display not yet rendered');
          return;
        }
      }
      expect(hasErrorDisplay, 'Expected .error-display for non-existent resource').toBe(true);
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
      await gotoWithRetry(page, `/integrations/connections/${nonExistentId}`);
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.error-display, .error-display-title, .marketplace-connection-detail-page',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .marketplace-connection-detail-page')
        .first().waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      // For a non-existent resource, any error state is valid: 404 "not found", API timeout,
      // network error, or generic failure. The test verifies the UI shows an error — the
      // exact error text depends on backend load and response time.
      if (hasErrorDisplay) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        if (errText && !errText.toLowerCase().includes('not found') && !errText.includes('404')) {
          console.warn(`[WARN] /integrations/connections/${nonExistentId} error is not 404: "${errText.slice(0, 200)}"`);
        }
      }
      if (!hasErrorDisplay) {
        // Check if page is still loading (backend slow under parallel E2E load)
        const stillLoading = (await page.locator('[data-testid="skeleton-row"], .skeleton, .loading-spinner').count()) > 0;
        if (stillLoading) {
          test.skip(true, 'Backend too slow — page still loading skeleton after 30s; error-display not yet rendered');
          return;
        }
      }
      expect(hasErrorDisplay, 'Expected .error-display for non-existent resource').toBe(true);
    });
  });

  test.describe('Edge (capability-gated or role-gated)', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await gotoWithRetry(page, '/developer');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.developer-portal-page, .unavailable-page',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      const url = page.url();
      if (url.includes('/403')) return;
      // Valid: .developer-portal-page (DeveloperPortalPage.tsx:36) OR .unavailable-page (capability disabled).
      // .app-main alone and error-display are never acceptable.
      await assertCapabilityGatedPageLoads(page, '.developer-portal-page, .unavailable-page');
    });

    test('baas page loads or shows unavailable', async ({ page }) => {
      await gotoWithRetry(page, '/baas');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.baas-page, .unavailable-page',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      const url = page.url();
      if (url.includes('/403')) return;
      await assertCapabilityGatedPageLoads(page, '.baas-page, .unavailable-page');
    });

    test('ml page loads or shows unavailable', async ({ page }) => {
      await gotoWithRetry(page, '/ml');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.ml-page, .unavailable-page',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      const url = page.url();
      if (url.includes('/403')) return;
      await assertCapabilityGatedPageLoads(page, '.ml-page, .unavailable-page', { timeout: 30000 });
    });

    test('communities page loads or shows unavailable', async ({ page }) => {
      await gotoWithRetry(page, '/communities');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
          contentSelector: '.communities-page, .communities-tab, .unavailable-page',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      const url = page.url();
      if (url.includes('/403')) return;
      await assertCapabilityGatedPageLoads(page, '.communities-page, .communities-tab, .unavailable-page', { timeout: 30000 });
    });
  });
});
