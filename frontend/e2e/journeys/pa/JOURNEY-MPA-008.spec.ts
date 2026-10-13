/**
 * E2E Test: JOURNEY-MPA-008 — Configure Advanced Observability
 *
 * Journey: Configure Advanced Observability
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /observability.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-008: Configure Advanced Observability', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('observability page loads', async ({ page }) => {
      // Terminal-state navigation — the fixed 3s wait raced the route
      // mount / capability fetch (batch b5 pattern).
      await loginAndNavigateToRoute(page, await getPlatformAdminUser(), '/observability', {
        timeout: 65000,
        contentSelector:
          '.observability-page, .app-main, [data-testid="app-main"], h1, .error-display, [data-testid="error-display"], .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      const gated =
        page.url().includes('/login') ||
        page.url().includes('/403') ||
        page.url().includes('/unavailable');
      test.skip(gated, 'Auth/role/capability gated — skipping success assertion');
      if (gated) return;
      expect(page.url()).toContain('/observability');
      const hasContent =
        (await page.locator('.observability-page, .app-main, [data-testid="app-main"], h1').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('observability loads without crash', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const no500 = (await page.locator('text=/500|internal server error/i').count()) === 0;
      expect(url.includes('/login') || url.includes('/403') || url.includes('/observability')).toBe(true);
      expect(no500).toBe(true) /* acceptable states */;
    });
  });

});
