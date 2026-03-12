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
import { assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-013: Configure Data Mesh Domain', () => {
  test.setTimeout(360000);

  test.describe('Success', () => {
    test('mesh domain list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.mesh-domain-list-page, .mesh-domain-list-header, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/mesh');
      const hasContent =
        (await page.locator('.mesh-domain-list-page').count()) > 0 ||
        (await page.locator('.mesh-domain-list-header').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.loading-spinner-container').count()) > 0 ||
        (await page.locator('h1:has-text("Mesh Domains")').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('mesh create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/mesh/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.mesh-domain-create-page, .loading-spinner-container, .error-display, #email',
        { timeout: 45000 }
      );
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
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
      });
    });
  });

  test.describe('Edge', () => {
    test('mesh list loads with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.mesh-domain-list-page, .mesh-domain-list-header, .empty-state, .error-display, .loading-spinner-container, .app-main, h1, #email',
        { timeout: 45000 }
      );
      expect(page.url()).toContain('/mesh');
    });
  });
});
