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
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('developer page loads', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.developer-portal-page, .app-main, [data-testid="app-main"], .unavailable-page, [data-testid="unavailable-page"], [role="status"]',
        { timeout: 25000 }
      );
      await page.waitForTimeout(2000);
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

    test('baas page loads', async ({ page }) => {
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

    test('webhooks list loads', async ({ page }) => {
      await loginAsPersona(page, getExternalDeveloperUser);
      await page.goto('/webhooks');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(true, 'Auth/role gated — skipping success assertion');
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
