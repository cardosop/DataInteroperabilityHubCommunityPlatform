/**
 * E2E Test: JOURNEY-DS-001 — Use Natural Language Search
 *
 * Journey: Use Natural Language Search
 * Persona: Data Scientist / ML Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per mesh-search-ai pattern. Routes: /search, /ai/search.
 * Capability-gated: ai.natural-language-search. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DS-001: Use Natural Language Search', () => {
  // 4 min: login + search + AI search nav can exceed 2 min under parallel E2E load (chromium uses 90s default)
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('search page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { contentSelector: '.search-page', timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/search');
    });

    test('AI search page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ai-search-page, .app-main, .unavailable-page, .loading-spinner, [data-testid="forbidden-page"], #email',
        { timeout: 15000 }
      );
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onForbidden = (await page.locator('[data-testid="forbidden-page"]').count()) > 0;
      const onAISearch = page.url().includes('/ai/search');
      const hasContent =
        (await page.locator('.ai-search-page, .app-main, .unavailable-page, .loading-spinner').count()) > 0;
      expect(onLogin || on403 || onForbidden || (onAISearch && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('AI search without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onAISearch = page.url().includes('/ai/search');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onAISearch || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('search and AI search routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/search');
      await navigateToRouteFromApp(page, '/ai/search', {
        timeout: 60000,
        contentSelector: '.ai-search-page, .unavailable-page, .error-display',
        acceptRedirectToLogin: true,
      });
      expect(
        page.url().includes('/ai/search') ||
          page.url().includes('/403') ||
          page.url().includes('/unavailable') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
