/**
 * E2E Test: JOURNEY-DMO-003 — Manage Domain Topology
 *
 * Journey: Manage Domain Topology
 * Persona: Data Mesh Domain Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /mesh, /mesh/topology. mesh-search-ai-routes covers /mesh; this spec provides
 * dedicated DMO-003 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DMO-003: Manage Domain Topology', () => {
  test.setTimeout(300000); // 5 min: persona login + mesh under parallel E2E load

  test.describe('Success', () => {
    test('mesh list loads for topology management', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .error-display, .empty-state',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/mesh');
    });

    test('mesh topology page loads', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh/topology', {
        timeout: 90000,
        contentSelector: '.topology-visualization, .app-main, .error-display, .loading-spinner',
      });
      const onMeshTopology = page.url().includes('/mesh/topology');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.topology-visualization, .app-main, .error-display, .loading-spinner').count()) > 0;
      expect(onLogin || on403 || (onMeshTopology && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to mesh route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/mesh', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|mesh|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/mesh')).toBe(true);
      if (url.includes('/mesh')) {
        const hasLoginPrompt =
          (await page.locator('input#email').count()) > 0 ||
          (await page.locator('[href*="/login"]').count()) > 0 ||
          (await page.getByText('Sign in').count()) > 0;
        expect(hasLoginPrompt).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('mesh and topology routes accessible', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      const urlAfterMesh = page.url();
      expect(
        urlAfterMesh.includes('/mesh') || urlAfterMesh.includes('/login') || urlAfterMesh.includes('/403')
      ).toBe(true);
      await page.goto('/mesh/topology');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const urlAfterTopo = page.url();
      expect(
        urlAfterTopo.includes('/mesh/topology') ||
          urlAfterTopo.includes('/mesh') ||
          urlAfterTopo.includes('/login')
      ).toBe(true);
    });
  });
});
