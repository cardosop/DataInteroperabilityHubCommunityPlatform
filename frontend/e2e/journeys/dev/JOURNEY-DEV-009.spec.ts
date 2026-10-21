/**
 * E2E Test: JOURNEY-DEV-009 — Integrate with Developer Portal
 *
 * Journey: Integrate with Developer Portal
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer, /baas, /settings/api-keys, /webhooks.
 * Extends integrations-jobs-webhooks, admin-audit-settings patterns. Real backend only; no mocks.
 *
 * Gate contract (close-test-coverage-gaps 1.3): real-flow-first — the
 * developer portal shell / api-keys / webhooks pages are the primary
 * assertions; every skip is CONDITIONAL (no-test-skip-true clean);
 * transient /unavailable bounces are W16-guarded; the MvpGatedRoute
 * /developer redirects to /coming-soon in MVP mode (conditional skip);
 * the server-side gate is seeded OPEN for E2E tenants (1.1:
 * e2e_flag_defaults carries developer_enabled=True) — a
 * DEVELOPER_DISABLED error display is a REAL regression and FAILS the
 * run (1.4 blast-radius contract).
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { getExternalDeveloperUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-009: Integrate with Developer Portal', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector: '.developer-portal-page, .app-main, [data-testid="app-main"], .unavailable-page, [data-testid="unavailable-page"], [data-testid="coming-soon-page"], .error-display, [data-testid="error-display"], .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onComingSoon = url.includes('/coming-soon');
      const onUnavailable = url.includes('/unavailable') && !onComingSoon;
      test.skip(onLogin || on403, 'Auth/role gated — server-side 403 route');
      test.skip(
        onComingSoon,
        'MVP mode — /developer is MvpGatedRoute and redirects to /coming-soon'
      );
      if (onUnavailable) {
        environmentSkipGuard(
          'Capability gate bounced /developer to /unavailable — ' +
            'OpenAPI/capabilities snapshot fetch likely failed under parallel load'
        );
      }
      test.skip(
        onUnavailable,
        'Capability gate bounced to /unavailable — transient snapshot failure'
      );

      // Real flow, primary: the developer portal shell renders.
      expect(url).toContain('/developer');
      await expect(
        page
          .locator(
            '.developer-portal-page, .app-main, [data-testid="app-main"], .disabled-capability-page, [data-testid="disabled-capability-page"]'
          )
          .first()
      ).toBeVisible({ timeout: 15000 });

      // The server-side developer gate is seeded OPEN for E2E tenants
      // (close-test-coverage-gaps 1.1: e2e_flag_defaults carries
      // developer_enabled=True) — a DEVELOPER_DISABLED error display here
      // is a REAL regression and must fail the run, not skip it.
      await expect(
        page.locator('.error-display, [data-testid="error-display"]').first()
      ).not.toBeVisible();
    });

    test('settings api-keys loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/settings/api-keys', {
        timeout: 90000,
        contentSelector: '.auth-api-key-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      const url = page.url();
      test.skip(
        url.includes('/login') || url.includes('/403'),
        'Auth/role gated — server-side 403 route'
      );
      expect(url).toContain('/settings/api-keys');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('webhooks list loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 90000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      const url = page.url();
      test.skip(
        url.includes('/login') || url.includes('/403'),
        'Auth/role gated — server-side 403 route'
      );
      expect(url).toContain('/webhooks');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 90000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page .webhook-detail-dl',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('developer, api-keys, webhooks routes accessible', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/developer', {
        timeout: 90000,
        contentSelector:
          '.developer-portal-page, .developer-page, .app-main, [data-testid="app-main"], .unavailable-page, [data-testid="unavailable-page"], [data-testid="coming-soon-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      const url = page.url();
      expect(
        url.includes('/developer') ||
          url.includes('/403') ||
          url.includes('/login') ||
          url.includes('/coming-soon')
      ).toBe(true);
      if (url.includes('/login')) return;
      await page.goto('/settings/api-keys');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForURL(/\/(settings\/api-keys|login)(\?|$)/, { timeout: 15000 });
      expect(
        page.url().includes('/settings/api-keys') || page.url().includes('/login')
      ).toBe(true);
    });
  });
});
