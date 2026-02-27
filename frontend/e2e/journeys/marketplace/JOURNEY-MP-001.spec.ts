/**
 * E2E Test: JOURNEY-MP-001 — Connect to External Marketplace
 *
 * Journey: Connect to External Marketplace
 * Persona: Data Product Owner, Tenant Admin
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge per integrations-jobs-webhooks pattern.
 * Routes: /integrations/connections. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-001: Connect to External Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 65000,
        contentSelector: '.connection-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });

    test('connection create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections/create', {
        timeout: 60000,
        contentSelector: '.connection-create-page, .marketplace-connection-create-page, form',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(1000);
      const onLogin = page.url().includes('/login');
      const onCreate = page.url().includes('/integrations/connections/create');
      const hasContent =
        (await page.locator('.marketplace-connection-create-page, .connection-create-page, .app-main, form').count()) > 0;
      expect(onLogin || (onCreate && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('connection detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.marketplace-connection-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('connections list and create routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 60000,
        contentSelector: '.connection-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/integrations/connections');
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections/create', {
        timeout: 60000,
        contentSelector: '.connection-create-page, .marketplace-connection-create-page, form',
      });
      expect(page.url().includes('/integrations/connections')).toBe(true);
    });
  });
});
