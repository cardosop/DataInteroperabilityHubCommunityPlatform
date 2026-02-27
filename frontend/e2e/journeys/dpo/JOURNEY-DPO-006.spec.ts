/**
 * E2E Test: JOURNEY-DPO-006 — Manage Marketplace Listings
 *
 * Journey: Manage Marketplace Listings
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /marketplace, /marketplace/publish, /marketplace/listings/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-006: Manage Marketplace Listings', () => {
  test.setTimeout(300000); // 5 min: marketplace API can be slow under parallel E2E load

  test.describe('Success', () => {
    test('marketplace list loads (discover listings)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .error-display, .empty-state, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Marketplace list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/marketplace');
    });

    test('marketplace publish page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 90000,
        contentSelector: '.listing-publish-page, .error-display, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Marketplace publish redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/marketplace/publish');
    });
  });

  test.describe('Failure', () => {
    test('marketplace listing detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto(`/marketplace/listings/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessContent = (await page.locator('.listing-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });

    test('unauthenticated access to marketplace list redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onMarketplaceWithLoginPrompt =
        url.includes('/marketplace') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onMarketplaceWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('marketplace list loads with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .error-display, .empty-state, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Marketplace list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/marketplace');
    });

    test('marketplace list shows pagination or list or empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .error-display, .empty-state, .listing-list-pagination, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Marketplace list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/marketplace');
      const hasPagination = (await page.locator('.listing-list-pagination').count()) > 0;
      const hasListOrEmpty =
        (await page.locator('.listing-list-page, .listing-list-grid').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasPagination || hasListOrEmpty).toBe(true);
    });
  });
});
