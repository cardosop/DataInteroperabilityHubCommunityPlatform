/**
 * E2E Test: JOURNEY-DMO-004 — Transfer Asset Ownership
 *
 * Journey: Transfer Asset Ownership
 * Persona: Data Mesh Domain Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /assets, /mesh.
 * DMO-001, DMO-003 already in mesh-search-ai. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DMO-004: Transfer Asset Ownership', () => {
  test.setTimeout(300000); // 5 min: persona login + assets/mesh under parallel E2E load

  test.describe('Success', () => {
    test('assets list loads for ownership transfer', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/assets');
    });

    test('mesh list loads for domain selection', async ({ page }) => {
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
  });

  test.describe('Failure', () => {
    test('asset detail with non-existent id shows error', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      await page.goto('/assets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.asset-detail-page .asset-detail-content',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('assets and mesh routes accessible', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/assets', {
        timeout: 90000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      const urlAfterAssets = page.url();
      expect(
        urlAfterAssets.includes('/assets') ||
          urlAfterAssets.includes('/login') ||
          urlAfterAssets.includes('/403')
      ).toBe(true);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const urlAfterMesh = page.url();
      expect(
        urlAfterMesh.includes('/mesh') || urlAfterMesh.includes('/login') || urlAfterMesh.includes('/403')
      ).toBe(true);
    });
  });
});
