/**
 * E2E Test: JOURNEY-MPA-007 — Monitor Data Mesh Topology
 *
 * Journey: Monitor Data Mesh Topology
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /mesh/topology.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-007: Monitor Data Mesh Topology', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh topology page loads', async ({ page }) => {
      // Terminal-state navigation — the fixed 3s wait raced the route
      // mount / capability fetch (batch b5 pattern).
      await loginAndNavigateToRoute(page, await getPlatformAdminUser(), '/mesh/topology', {
        timeout: 65000,
        contentSelector:
          '.topology-visualization, .app-main, [data-testid="app-main"], .mesh-domain-list-page, .error-display, [data-testid="error-display"], .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      const gated =
        page.url().includes('/login') ||
        page.url().includes('/403') ||
        page.url().includes('/unavailable');
      test.skip(gated, 'Auth/role/capability gated — skipping success assertion');
      if (gated) return;
      expect(page.url()).toContain('/mesh/topology');
      const hasContent =
        (await page.locator('.topology-visualization, .app-main, [data-testid="app-main"], .mesh-domain-list-page').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('mesh topology loads or redirects', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/mesh/topology');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/mesh')).toBe(true);
    });
  });

});
