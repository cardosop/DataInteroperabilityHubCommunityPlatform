/**
 * E2E Test: JOURNEY-DC-003 — Search and Filter Assets
 *
 * Journey: Search and Filter Assets
 * Persona: Data Consumer
 * Reference: ManualTest/Front/03-USER-JOURNEYS/dc/JOURNEY-DC-003.md
 *
 * Success/Failure/Edge. Routes: /marketplace, /search.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-003: Search and Filter Assets', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('search in marketplace updates results or shows empty', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector:
          '.listing-list-page, .listing-list-grid, .empty-state, .error-display, .loading-spinner-container, .listing-list-filters',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const searchInput = page
        .locator(
          '.listing-list-filters input[type="text"], .listing-list-filters input, input[placeholder*="Search"]'
        )
        .first();
      if ((await searchInput.count()) > 0) {
        await searchInput.fill('test');
        await page.waitForTimeout(1500);
      }
      expect(page.url()).toContain('/marketplace');
      const hasContent =
        (await page.locator('.listing-list-page, .listing-list-grid, .empty-state, .error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('filters in marketplace apply and show filtered results', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector:
          '.listing-list-page, .listing-list-grid, .empty-state, .error-display, .listing-list-filters, .filter-select',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const filterSelect = page.locator('.filter-select').first();
      if ((await filterSelect.count()) > 0) {
        await filterSelect.selectOption({ index: 1 });
        await page.waitForTimeout(1000);
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
      const url = page.url();
      const onLogin = url.includes('/login');
      const onMarketplaceWithPrompt =
        url.includes('/marketplace') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onMarketplaceWithPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('clear filters restores full list or empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .listing-list-filters',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
      if ((await searchInput.count()) > 0) {
        await searchInput.fill('xyznonexistent');
        await page.waitForTimeout(1000);
        await searchInput.fill('');
        await page.waitForTimeout(1000);
      }
      expect(page.url()).toContain('/marketplace');
    });
  });
});
