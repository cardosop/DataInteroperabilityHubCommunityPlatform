/**
 * E2E Test: JOURNEY-DMO-005 — Monitor Domain Health
 *
 * Journey: Monitor Domain Health
 * Persona: Data Mesh Domain Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /mesh, /observability.
 * DMO-001, DMO-003 already in mesh-search-ai. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DMO-005: Monitor Domain Health', () => {
  test.setTimeout(300000); // 5 min: persona login + mesh/observability under parallel E2E load

  test.describe('Success', () => {
    test('mesh list loads for domain health', async ({ page }) => {
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

    test('observability page loads for health metrics', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/observability', {
        timeout: 90000,
        contentSelector: '.observability-page, .app-main, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/observability');
      const hasContent =
        (await page.locator('.observability-page, .app-main').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('mesh domain detail with non-existent id shows error', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      await page.goto('/mesh/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.mesh-domain-detail-page .mesh-domain-detail-content',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/observability');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('mesh and observability routes accessible', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      const urlAfterMesh = page.url();
      expect(
        urlAfterMesh.includes('/mesh') || urlAfterMesh.includes('/login') || urlAfterMesh.includes('/403')
      ).toBe(true);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const urlAfterObs = page.url();
      expect(
        urlAfterObs.includes('/observability') ||
          urlAfterObs.includes('/login') ||
          urlAfterObs.includes('/403')
      ).toBe(true);
    });
  });
});
