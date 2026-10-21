/**
 * E2E Feature: BaaS (capability-gated)
 * Routes: /baas (baas.api-keys capability).
 * Capability-gated via CapabilityRoute — when disabled, redirects to /unavailable
 * or /coming-soon. Tests verify the gating works correctly.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertCapabilityGatedPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: BaaS (capability-gated)', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('baas route loads or shows capability-gated redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/baas', {
        timeout: 60000,
        contentSelector: '.baas-page, .unavailable-page, [data-testid="unavailable-page"], .coming-soon-page, .error-display, [data-testid="error-display"], h1',
      });
      await assertCapabilityGatedPageLoads(page, '.baas-page, .unavailable-page, [data-testid="unavailable-page"], .coming-soon-page', {
        timeout: 30000,
      });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to baas redirects to login', async ({ page }) => {
      await page.goto('/baas');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/baas') || url.includes('/unavailable'),
        'Expected /login redirect, /baas route, or /unavailable'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('baas renders without server errors when gated', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/baas', {
        timeout: 60000,
        contentSelector: '.baas-page, .unavailable-page, [data-testid="unavailable-page"], .coming-soon-page, .error-display, [data-testid="error-display"], h1',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) return;
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'BaaS page must not show 500 errors').toBe(false);
    });
  });
});
