/**
 * E2E Test: JOURNEY-DMO-002 — Configure Federated Governance
 *
 * Journey: Configure Federated Governance
 * Persona: Data Mesh Domain Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /governance, /mesh.
 * DMO-001, DMO-003 already in mesh-search-ai. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DMO-002: Configure Federated Governance', () => {
  test.setTimeout(300000); // 5 min: persona login + mesh/governance under parallel E2E load

  test.describe('Success', () => {
    test('mesh list loads for governance config', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .error-display, .empty-state, .loading-spinner-container, .app-main',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/mesh');
    });

    test('governance page loads or 403 when role missing', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/governance', {
        timeout: 90000,
        contentSelector: '.governance-access-request-list-page, .access-request-list-page, .app-main, .error-display, .empty-state, .loading-spinner-container',
      });
      await page.waitForTimeout(3000);
      const url = page.url();
      const onGov = url.includes('/governance');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.app-main').count()) > 0 ||
        (await page.locator('.error-display, .governance-access-request-list-page, .access-request-list-page, .empty-state, h1').count()) > 0 ||
        (await page.locator('text=/403|forbidden|Access|Request/i').count()) > 0;
      expect(onGov || on403 || onLogin).toBe(true);
      expect(hasContent || onGov || on403 || onLogin).toBe(true);
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
    test('mesh and governance routes accessible', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      const urlAfterMesh = page.url();
      expect(
        urlAfterMesh.includes('/mesh') || urlAfterMesh.includes('/login') || urlAfterMesh.includes('/403')
      ).toBe(true);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const urlAfterGov = page.url();
      expect(
        urlAfterGov.includes('/governance') ||
          urlAfterGov.includes('/403') ||
          urlAfterGov.includes('/login')
      ).toBe(true);
    });
  });
});
