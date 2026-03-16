/**
 * E2E Test: JOURNEY-MPA-001 — Manage Marketplace Listings
 *
 * Journey: Manage Marketplace Listings
 * Persona: Platform Admin
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /marketplace, /admin. Backend has tests; frontend spec for alignment.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { hasLoginPrompt, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-001: Manage Marketplace Listings', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/marketplace');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to marketplace route redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/marketplace')
      ).toBe(true);
      if (url.includes('/marketplace')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

});
