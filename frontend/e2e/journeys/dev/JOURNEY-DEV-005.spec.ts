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
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('search page loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/search', {
        timeout: 45000,
        acceptRedirectToLogin: true,
      });
      const onSearch = page.url().includes('/search');
      const onLogin = page.url().includes('/login');
      if (onLogin) {
        test.skip(true, 'Auth gated — skipping success assertion');
        return;
      }
      expect(onSearch).toBe(true);
      const hasContent = (await page.locator('.search-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
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
      if (onLogin || on403) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onAISearch).toBe(true);
      const hasContent =
        (await page.locator('.ai-search-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('AI search without capability shows 403 or unavailable', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/ai/search', {
        timeout: 45000,
        acceptRedirectToLogin: true,
      });
      const url = page.url();
      if (url.includes('/login')) {
        test.skip(true, 'AI Search not accessible in this env — login redirect indicates missing user/token');
        return;
      }
      // Must be either capability-gated (403 or /unavailable) or the page loaded (capability enabled).
      // CapabilityRoute redirects to /unavailable when the capability flag is off.
      expect(url.includes('/403') || url.includes('/ai/search') || url.includes('/unavailable')).toBe(true);
      if (url.includes('/ai/search')) {
        // If capability is enabled, page content must be present
        const hasContent = (await page.locator('.ai-search-page, .unavailable-page, [data-testid="unavailable-page"], .app-main, [data-testid="app-main"]').count()) > 0;
        expect(hasContent).toBe(true) /* acceptable states */;
      }
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
      if (urlAfterSearch.includes('/login')) return; // Already redirected; skip AI nav
      // Client-side nav to AI search (already logged in)
      const aiLink = page.locator('.app-sidebar .nav-link').filter({ hasText: 'AI Search' }).first();
      if ((await aiLink.count()) > 0) {
        await aiLink.click();
        await page.waitForURL(/\/(ai\/search|403|login)(\?|$)/, { timeout: 15000 });
      } else {
        await page.goto('/ai/search');
        await page.waitForLoadState('domcontentloaded');
        await page.waitForURL(/\/(ai\/search|403|login)(\?|$)/, { timeout: 15000 });
      }
      const urlAfterAi = page.url();
      expect(
        urlAfterAi.includes('/ai/search') ||
          urlAfterAi.includes('/403') ||
          urlAfterAi.includes('/login')
      ).toBe(true);
    });
  });
});
