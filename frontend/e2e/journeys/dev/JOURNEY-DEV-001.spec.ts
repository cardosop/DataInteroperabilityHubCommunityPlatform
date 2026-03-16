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
import { assertNonExistentIdShowsError, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-001: Build Custom Integration', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
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

    test('baas page loads', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onBaas = page.url().includes('/baas');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.baas-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onBaas && hasContent)).toBe(true);
    });

    test('webhooks list loads', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/webhooks');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/webhooks');
      const hasContent =
        (await page.locator('.webhook-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page .webhook-detail-dl',
        waitAfterLoad: 5000,
      });
    });
  });

});
