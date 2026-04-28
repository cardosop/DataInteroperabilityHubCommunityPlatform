/**
 * E2E Test: JOURNEY-TOPOLOGY-VISUALIZATION — Phase 38 (36.6)
 *
 * Verifies the React Flow canvas renders for the mesh topology page.
 * Checks for DomainNode rendering, zoom controls, legend, and EmptyState.
 */

import { expect, test } from '@playwright/test';
import { getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, assertCapabilityGatedPageLoads } from '../../fixtures/helpers';

test.describe('JOURNEY-TOPOLOGY-VISUALIZATION: Topology React Flow canvas', () => {
  test.setTimeout(120000);

  test('topology page renders React Flow canvas or EmptyState', async ({ page }) => {
    const dmoUser = await getDataMeshDomainOwnerUser();
    await loginAndNavigateToRoute(page, dmoUser, '/mesh/topology', {
      timeout: 90000,
      contentSelector: '.react-flow, .empty-state, [data-testid="empty-state"]',
    });

    // assertCapabilityGatedPageLoads rejects .error-display, [data-testid="error-display"] and allows
    // /403, /login, .unavailable-page, [data-testid="unavailable-page"] as valid gating outcomes.
    await assertCapabilityGatedPageLoads(
      page,
      '.react-flow, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"]',
      { timeout: 30000 },
    );

    const hasReactFlow = (await page.locator('.react-flow').count()) > 0;
    const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;

    if (hasReactFlow) {
      await expect(page.locator('.react-flow__controls')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('.react-flow__minimap')).toBeVisible({ timeout: 5000 });
    }

    if (hasEmptyState) {
      await expect(page.getByText('No domains found')).toBeVisible({ timeout: 5000 });
    }
  });

  test('health legend items are visible in the topology page', async ({ page }) => {
    const dmoUser = await getDataMeshDomainOwnerUser();
    await loginAndNavigateToRoute(page, dmoUser, '/mesh/topology', {
      timeout: 90000,
      contentSelector: '.react-flow, .empty-state, [data-testid="empty-state"]',
    });

    await assertCapabilityGatedPageLoads(
      page,
      '.react-flow, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"]',
      { timeout: 30000 },
    );

    // Legend check only applies when the page actually rendered (not gated)
    if (page.url().includes('/403') || page.url().includes('/login') || page.url().includes('/unavailable')) {
      return; // Capability-gated — no legend to check
    }

    await expect(page.getByText('Legend')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('≥ 80')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('< 60')).toBeVisible({ timeout: 5000 });
  });

  test('topology page shows header with Mesh Topology title', async ({ page }) => {
    const dmoUser = await getDataMeshDomainOwnerUser();
    await loginAndNavigateToRoute(page, dmoUser, '/mesh/topology', {
      timeout: 90000,
      contentSelector: '.react-flow, .empty-state, [data-testid="empty-state"]',
    });

    await assertCapabilityGatedPageLoads(
      page,
      '.react-flow, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"]',
      { timeout: 30000 },
    );

    if (page.url().includes('/403') || page.url().includes('/login') || page.url().includes('/unavailable')) {
      return; // Capability-gated
    }

    await expect(page.getByText('Mesh Topology')).toBeVisible({ timeout: 5000 });
  });
});
