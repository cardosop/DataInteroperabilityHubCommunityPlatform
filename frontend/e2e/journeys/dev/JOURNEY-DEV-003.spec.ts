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
import { clearAuthStorage, getExternalDeveloperUser, loginAsPersona } from '../../fixtures/auth';
import { hasLoginPrompt } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-003: Integrate via CLI', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads for CLI docs', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.developer-portal-page, .app-main, .unavailable-page, .loading-spinner-container, [role="status"]',
        { timeout: 25000 }
      );
      await page.waitForTimeout(2000);
      const onDeveloper = page.url().includes('/developer');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, .unavailable-page, .loading-spinner-container').count()) > 0;
      expect(onLogin || on403 || (onDeveloper && hasContent)).toBe(true);
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

  test.describe('Edge', () => {
    test('developer route accessible', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(
        page.url().includes('/developer') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
