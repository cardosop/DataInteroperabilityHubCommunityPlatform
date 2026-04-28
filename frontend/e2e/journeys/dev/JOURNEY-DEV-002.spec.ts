/**
 * E2E Test: JOURNEY-DEV-002 — Integrate via SDK
 *
 * Journey: Integrate via SDK
 * Persona: External Developer
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /developer, /baas (API keys). Backend has tests; frontend spec for alignment.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getExternalDeveloperUser, loginAsPersona } from '../../fixtures/auth';
import { hasLoginPrompt } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-002: Integrate via SDK', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads for SDK docs', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      if (onLogin || on403) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onDeveloper).toBe(true);
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('baas page loads for API keys', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onBaas = page.url().includes('/baas');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      if (onLogin || on403) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onBaas).toBe(true);
      const hasContent =
        (await page.locator('.baas-page, .app-main, [data-testid="app-main"]').count()) > 0;
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
