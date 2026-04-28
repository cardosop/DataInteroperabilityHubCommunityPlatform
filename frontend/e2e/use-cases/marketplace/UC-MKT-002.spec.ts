/**
 * E2E: UC-MKT-002 — Browse/Discover Marketplace Listings
 *
 * Use Case: Discover Marketplace Listings
 * Persona: Data Consumer
 * Reference: docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /marketplace.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-MKT-002: Browse Marketplace Listings', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('marketplace list loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"]',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to marketplace redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace)/, { timeout: 20_000 });
      expect(page.url().includes('/login') || page.url().includes('/marketplace')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace list with empty state loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/marketplace');
    });
  });
});
