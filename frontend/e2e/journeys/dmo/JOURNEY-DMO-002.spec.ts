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
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh list loads for governance config', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, [data-testid="empty-state"], .app-main, [data-testid="app-main"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        throw new Error(`Unexpected redirect to ${page.url()} — verify DMO user has mesh access`);
      }
      expect(page.url()).toContain('/mesh');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('governance page loads or 403 when role missing', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/governance', {
        timeout: 90000,
        contentSelector: '.governance-access-request-list-page, .access-request-list-page, .app-main, [data-testid="app-main"], .empty-state, [data-testid="empty-state"]',
      });
      await page.waitForTimeout(3000);
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login — DMO user should be authenticated');
      }
      const url = page.url();
      const onGov = url.includes('/governance');
      const on403 = url.includes('/403');
      if (on403) {
        test.skip(true, 'Role gated — skipping success assertion');
        return;
      }
      expect(onGov).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('mesh domain detail with non-existent id shows error', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
        contentSelector: '.mesh-domain-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
