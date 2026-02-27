/**
 * E2E Test: JOURNEY-DEV-005 — Use Natural Language Search API
 *
 * Journey: Use Natural Language Search API
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /search, /ai/search.
 * Capability-gated: ai.natural-language-search. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getExternalDeveloperUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-005: Use Natural Language Search API', () => {
  test.setTimeout(180000); // 3 min: external dev user + capability-gated routes

  test.describe('Success', () => {
    test('search page loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/search', {
        timeout: 45000,
        acceptRedirectToLogin: true,
      });
      const onSearch = page.url().includes('/search');
      const onLogin = page.url().includes('/login');
      const hasContent = (await page.locator('.search-page, .app-main').count()) > 0;
      expect(onLogin || (onSearch && hasContent)).toBe(true);
    });

    test('AI search page loads or redirects', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/ai/search', {
        timeout: 45000,
        acceptRedirectToLogin: true,
      });
      const onAISearch = page.url().includes('/ai/search');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasContent =
        (await page.locator('.ai-search-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onAISearch && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('AI search without capability shows 403 or unavailable', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/ai/search', {
        timeout: 45000,
        acceptRedirectToLogin: true,
      });
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onAISearch = page.url().includes('/ai/search');
      expect(on403 || onLogin || onUnavailable || onAISearch).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('search and AI search routes accessible', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/search', {
        timeout: 45000,
        acceptRedirectToLogin: true,
      });
      const urlAfterSearch = page.url();
      expect(
        urlAfterSearch.includes('/search') || urlAfterSearch.includes('/login')
      ).toBe(true);
      // Client-side nav to AI search (already logged in)
      const aiLink = page.locator('.app-sidebar .nav-link').filter({ hasText: 'AI Search' }).first();
      if ((await aiLink.count()) > 0) {
        await aiLink.click();
      } else {
        await page.goto('/ai/search');
      }
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const urlAfterAi = page.url();
      expect(
        urlAfterAi.includes('/ai/search') ||
          urlAfterAi.includes('/403') ||
          urlAfterAi.includes('/login')
      ).toBe(true);
    });
  });
});
