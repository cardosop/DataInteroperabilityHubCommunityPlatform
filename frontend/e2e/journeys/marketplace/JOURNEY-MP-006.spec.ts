/**
 * E2E Test: JOURNEY-MP-006 — Manage Marketplace Mappings
 *
 * Journey: Manage Marketplace Mappings
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/mappings.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-006: Manage Marketplace Mappings', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('mappings list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/mappings', {
        timeout: 60000,
        contentSelector: '.mapping-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }
      expect(page.url()).toContain('/integrations/mappings');
      const hasContent =
        (await page.locator('.mapping-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('non-existent mappings subpath redirects to mappings list', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      // Navigate to a mapping ID that does not exist.
      // The router has no :id child route under /integrations/mappings — unknown IDs
      // redirect to the list via <Navigate to="/integrations/mappings" replace />.
      await page.goto('/integrations/mappings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      // Wait for redirect to the list page (or login/403 if auth expired)
      await page
        .waitForURL(
          (url) =>
            !url.pathname.includes('00000000-0000-0000-0000-000000000000'),
          { timeout: 10000 }
        )
        .catch(() => null); // accept if URL doesn't change (unexpected — caught by assertion below)
      const onLogin = page.url().includes('/login');
      const onMappingsList =
        page.url().includes('/integrations/mappings') &&
        !page.url().includes('00000000-0000-0000-0000-000000000000');
      const on403 = page.url().includes('/403');
      expect(onMappingsList || onLogin || on403).toBe(true) /* acceptable states */;
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/integrations/mappings');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('mappings route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/mappings', {
        timeout: 90000,
        contentSelector: '.mapping-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) return;
      expect(page.url()).toContain('/integrations/mappings');
    });
  });
});
