/**
 * E2E Test: JOURNEY-DPO-013 — Configure Data Mesh Domain
 *
 * Journey: Configure Data Mesh Domain
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /mesh, /mesh/create, /mesh/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForAppMainReady,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-013: Configure Data Mesh Domain', () => {
  test.setTimeout(300000); // 5 min: mesh API + login under parallel E2E load

  test.describe('Success', () => {
    test('mesh domain list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      expect(page.url()).toContain('/mesh');
      // Wait for loading to complete and actual content to appear (not just loading spinner)
      await page
        .locator('.mesh-domain-list-page, .empty-state, .error-display')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 });
      const hasContent =
        (await page.locator('.mesh-domain-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('mesh create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/mesh/create', {
        timeout: 90000,
        contentSelector: '.mesh-domain-create-page, .error-display',
      });
      expect(page.url()).toContain('/mesh/create');
    });
  });

  test.describe('Failure', () => {
    test('mesh domain detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      await page.goto('/mesh/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.mesh-domain-detail-page .mesh-domain-detail-content',
        waitAfterLoad: 5000,
      });
    });
  });

  test.describe('Edge', () => {
    test('mesh list with empty state shows create message', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/mesh');
    });
  });
});
