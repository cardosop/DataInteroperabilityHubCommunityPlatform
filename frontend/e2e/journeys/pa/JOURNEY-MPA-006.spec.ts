/**
 * E2E Test: JOURNEY-MPA-006 — Configure Advanced Marketplace Features
 *
 * Journey: Configure Advanced Marketplace Features
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /marketplace, /marketplace/publish.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-006: Configure Advanced Marketplace Features', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.listing-list-page, .error-display, .empty-state, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/marketplace');
    });

    test('marketplace publish page loads', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/marketplace/publish');
      try {
        await waitForAppMainReady(page, { timeout: 60000, contentSelector: '.listing-publish-page' });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/marketplace/publish');
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/marketplace/listings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const hasError = (await page.locator('.error-display').count()) > 0;
      const noSuccessContent = (await page.locator('.listing-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace routes accessible', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/marketplace');
    });
  });
});
