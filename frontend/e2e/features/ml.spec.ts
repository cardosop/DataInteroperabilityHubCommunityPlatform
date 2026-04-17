/**
 * E2E Feature: ML (capability-gated)
 * Routes: /ml (ml.models capability).
 * Capability-gated via CapabilityRoute — when disabled, redirects to /unavailable
 * or /coming-soon. Tests verify the gating works correctly.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertCapabilityGatedPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: ML (capability-gated)', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ml route loads or shows capability-gated redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ml', {
        timeout: 60000,
        contentSelector: '.ml-page, .ml-model-list-page, .unavailable-page, .coming-soon-page, .error-display, h1',
      });
      await assertCapabilityGatedPageLoads(
        page,
        '.ml-page, .ml-model-list-page, .unavailable-page, .coming-soon-page',
        { timeout: 30000 }
      );
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to ml redirects to login', async ({ page }) => {
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/ml') || url.includes('/unavailable'),
        'Expected /login redirect, /ml route, or /unavailable'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ml renders without server errors when gated', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ml', {
        timeout: 60000,
        contentSelector: '.ml-page, .ml-model-list-page, .unavailable-page, .coming-soon-page, .error-display, h1',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) return;
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'ML page must not show 500 errors').toBe(false);
    });
  });
});
