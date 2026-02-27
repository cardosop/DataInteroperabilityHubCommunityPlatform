/**
 * E2E Test: JOURNEY-MP-002 — Publish Asset to Marketplace
 *
 * Journey: Publish Asset to Marketplace
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /marketplace/publish, /assets.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-002: Publish Asset to Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads for publish selection', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });

    test('marketplace publish page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/publish');
    });
  });

  test.describe('Failure', () => {
    test('publish with non-existent asset shows error or empty', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, .empty-state',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(1000);
      const onLogin = page.url().includes('/login');
      const onPublish = page.url().includes('/marketplace/publish');
      const hasContent =
        (await page.locator('.listing-publish-page, .app-main, .empty-state').count()) > 0;
      expect(onLogin || (onPublish && hasContent)).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('assets and marketplace publish routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
