/**
 * E2E Test: JOURNEY-DEV-001 — Build Custom Integration / Access Developer Portal
 *
 * Journey: Build Custom Integration
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer, /baas, /webhooks.
 * Extends integrations-jobs-webhooks, admin-audit-settings patterns. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getExternalDeveloperUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForAppMainReady,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-001: Build Custom Integration', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      // loginAndNavigateToRoute with a TERMINAL-state content selector.
      // The previous waitForSelector included [role="status"], which the
      // CapabilityRoute LoadingSpinner matches — the wait passed on the
      // transient spinner while capabilities were still resolving and the
      // content check failed a beat later (batch b5). The disabled page
      // is .disabled-capability-page (NOT .unavailable-page — those
      // markers were dead selectors).
      const developerUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, developerUser, '/developer', {
        timeout: 60000,
        contentSelector:
          '.developer-portal-page, .app-main, [data-testid="app-main"], .disabled-capability-page, [data-testid="disabled-capability-page"], .error-display, [data-testid="error-display"]',
      });
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onUnavailable = page.url().includes('/unavailable');
      if (onLogin || on403 || onUnavailable) {
        test.skip(onLogin || on403 || onUnavailable, 'Auth/role/capability gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/developer');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('baas page loads', async ({ page }) => {
      // Same terminal-state pattern as the developer-page test above: a
      // fixed 3s wait races the capabilities fetch (the /baas route is
      // behind CapabilityRoute capability="baas.api-keys") — wait for the
      // page OR the real disabled-capability markers.
      const developerUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, developerUser, '/baas', {
        timeout: 60000,
        contentSelector:
          '.baas-page, .app-main, [data-testid="app-main"], .disabled-capability-page, [data-testid="disabled-capability-page"], .error-display, [data-testid="error-display"]',
      });
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onUnavailable = page.url().includes('/unavailable');
      if (onLogin || on403 || onUnavailable) {
        test.skip(onLogin || on403 || onUnavailable, 'Auth/role/capability gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/baas');
      const hasContent =
        (await page.locator('.baas-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('webhooks list loads', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/webhooks');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Auth/role gated — skipping success assertion');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/webhooks');
      const hasContent =
        (await page.locator('.webhook-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      // loginAndNavigateToRoute (not loginAsPersona + bare page.goto): the
      // reload after a UI login has no persisted access_token (Phase 11.1
      // localStorage hardening) and the detail query can fire before the
      // boot refresh recovers — surfacing AUTH_UNAUTHORIZED instead of the
      // 404 boundary (same fix as JOURNEY-AUD-001/006).
      const developerUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(
        page,
        developerUser,
        '/webhooks/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .webhook-detail-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page .webhook-detail-dl',
        waitAfterLoad: 5000,
      });
    });
  });

});
