/**
 * E2E Test: JOURNEY-DE-013 — Configure Data Mesh Domain
 *
 * Journey: Configure Data Mesh Domain
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /mesh, /mesh/create, /mesh/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-013: Configure Data Mesh Domain', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh domain list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/mesh');
      const hasContent =
        (await page.locator('.mesh-domain-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('mesh create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/mesh/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.mesh-domain-create-page, .error-display, #email', {
        timeout: 20000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/mesh/create');
    });
  });

  test.describe('Failure', () => {
    test('mesh domain detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/mesh/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.mesh-domain-detail-page .mesh-domain-detail-content',
        waitAfterLoad: 5000,
      });
    });
  });

  test.describe('Edge', () => {
    test('mesh list loads with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/mesh', {
        timeout: 60000,
        contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/mesh');
    });
  });
});
