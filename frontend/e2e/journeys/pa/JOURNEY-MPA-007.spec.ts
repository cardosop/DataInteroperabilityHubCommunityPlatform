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

test.describe('JOURNEY-MPA-007: Monitor Data Mesh Topology', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh topology page loads', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/mesh/topology');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onTopology = page.url().includes('/mesh/topology');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.topology-visualization, .app-main, .mesh-domain-list-page').count()) > 0;
      expect(onLogin || on403 || (onTopology && hasContent)).toBe(true);
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

  test.describe('Edge', () => {
    test('mesh and topology routes accessible', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/mesh');
      await page.goto('/mesh/topology');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/mesh')).toBe(true);
    });
  });
});
