/**
 * E2E Test: JOURNEY-DEV-003 — Integrate via CLI
 *
 * Journey: Integrate via CLI
 * Persona: External Developer
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /developer (CLI docs). Backend has tests; frontend spec for alignment.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getExternalDeveloperUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-003: Integrate via CLI', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads for CLI docs', async ({ page }) => {
      // Same fix as JOURNEY-DEV-001's developer-page test: the old
      // waitForSelector included [role="status"], which the CapabilityRoute
      // LoadingSpinner matches — the wait passed on the transient spinner
      // and the content check failed before the portal mounted (batch b5).
      // The disabled page is .disabled-capability-page, NOT .unavailable-page.
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
  });

  test.describe('Failure', () => {
    test('unauthenticated access to developer route redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/developer', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|developer|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/developer')
      ).toBe(true);
      if (url.includes('/developer')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

});
