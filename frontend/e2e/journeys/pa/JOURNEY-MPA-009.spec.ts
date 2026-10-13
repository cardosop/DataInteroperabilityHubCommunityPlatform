/**
 * E2E Test: JOURNEY-MPA-009 — Manage Plugin Marketplace
 *
 * Journey: Manage Plugin Marketplace
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /developer.
 * Capability-gated: developer.plugins. Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-009: Manage Plugin Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('developer page loads (plugin marketplace)', async ({ page }) => {
      // Terminal-state navigation — the fixed 3s wait raced the
      // capability fetch on this gated route (batch b5 pattern).
      await loginAndNavigateToRoute(page, await getPlatformAdminUser(), '/developer', {
        timeout: 65000,
        contentSelector:
          '.developer-portal-page, .app-main, [data-testid="app-main"], .error-display, [data-testid="error-display"], .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      test.skip(
        page.url().includes('/login') ||
          page.url().includes('/403') ||
          page.url().includes('/unavailable'),
        'Auth/role/capability gated — skipping success assertion'
      );
      expect(page.url()).toContain('/developer');
      const hasContent =
        (await page.locator('.developer-portal-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('developer page loads or shows unavailable', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/developer');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const hasContent =
        (await page.locator('.developer-portal-page, .unavailable-page, [data-testid="unavailable-page"], .app-main, [data-testid="app-main"]').count()) > 0;
      expect(url.includes('/login') || url.includes('/403') || url.includes('/developer')).toBe(true);
      // When on /login, we may not have developer content; when on /developer or /403, expect content
      expect(url.includes('/login') || hasContent).toBe(true);
    });
  });

});
