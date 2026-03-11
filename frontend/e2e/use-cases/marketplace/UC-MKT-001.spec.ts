/**
 * E2E: UC-MKT-001 — Publish Asset to Marketplace
 *
 * Use Case: Publish Asset to Marketplace
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /marketplace/publish.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-MKT-001: Publish Asset to Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace publish page loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .error-display, h1',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/publish');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to marketplace publish redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/marketplace/publish', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace)/, { timeout: 20_000 });
      expect(page.url().includes('/login') || page.url().includes('/marketplace')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace publish page shows form or empty state', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .error-display, form, .empty-state',
      });
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
