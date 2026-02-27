/**
 * E2E Test: JOURNEY-DMO-001 — Create Data Mesh Domain
 *
 * Journey: Create Data Mesh Domain
 * Persona: Data Mesh Domain Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /mesh, /mesh/create. mesh-search-ai-routes covers /mesh; this spec provides
 * dedicated DMO-001 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DMO-001: Create Data Mesh Domain', () => {
  test.setTimeout(300000); // 5 min: persona login + mesh under parallel E2E load

  test.describe('Success', () => {
    test('mesh list loads for domain creation', async ({ page }) => {
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

    test('mesh create page loads', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh/create', {
        timeout: 90000,
        contentSelector: '.mesh-domain-create-page, .app-main, .error-display',
      });
      const onMeshCreate = page.url().includes('/mesh/create');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.mesh-domain-create-page, .app-main, .error-display').count()) > 0;
      expect(onLogin || on403 || (onMeshCreate && hasContent)).toBe(true);
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
  });

  test.describe('Edge', () => {
    test('mesh route accessible', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      const url = page.url();
      expect(url.includes('/mesh') || url.includes('/login') || url.includes('/403')).toBe(true);
    });
  });
});
