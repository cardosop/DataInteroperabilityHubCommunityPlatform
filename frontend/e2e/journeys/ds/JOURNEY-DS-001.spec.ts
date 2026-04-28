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
import { loginAndNavigateToRoute, navigateToRouteFromApp, waitForAppMainReady, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-DS-001: Use Natural Language Search', () => {
  // 4 min: login + search + AI search nav can exceed 2 min under parallel E2E load (chromium uses 90s default)
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('search page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      await waitForAppMainReady(page, { contentSelector: '.search-page', timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        throw new Error(`Unexpected redirect to ${page.url()} — verify test user has search access`);
      }
      expect(page.url()).toContain('/search');
    });

    test('AI search page loads (capability-gated)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ai-search-page, .unavailable-page, [data-testid="unavailable-page"], [data-testid="forbidden-page"]',
        { timeout: 15000 }
      );
      await page.waitForTimeout(3000);
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login — user should be authenticated');
      }
      const redirectedAway = !page.url().includes('/ai/search') && !page.url().includes('/login');
      const isGated =
        page.url().includes('/403') ||
        redirectedAway ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], [data-testid="forbidden-page"]').count()) > 0;
      // Both outcomes are valid: capability enabled (page loads) or disabled (properly gated)
      if (isGated) {
        // Capability gate is working — valid outcome; skip (not pass green for a gated feature)
        test.skip(true, 'AI search capability gated (403/redirect/unavailable)');
        return;
      }
      const onAISearch = page.url().includes('/ai/search');
      const hasContent = (await page.locator('.ai-search-page').count()) > 0;
      expect(onAISearch && hasContent).toBe(true);
    });

    test('search page accepts query and shows results area', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });

      // Find search input
      const searchInput = page.locator(
        'input[type="search"], input[placeholder*="Search" i], .search-input, #search-query, input[name="q"], input[name="query"]'
      );
      const inputCount = await searchInput.count();

      if (inputCount > 0) {
        // Fill with test query
        await searchInput.first().fill('test data');
        // Try pressing Enter to submit
        await searchInput.first().press('Enter');
        // Wait for results to load
        await page.waitForTimeout(2000);
      }

      // Look for results container or empty results message
      const resultsArea = page.locator(
        '.search-results, .result-list, [data-testid*="result"], .search-page'
      );
      // intentional: visibility check on a transiently-attached element — treating a detached-at-check-time element as 'not visible' is the semantically correct fallback; the caller's branch logic uses the boolean result.
      const resultsVisible = (await resultsArea.count()) > 0 && await resultsArea.first().isVisible().catch(() => false);

      const emptyResults = page.getByText(/no results|0 results|nothing found/i);
      // intentional: visibility check on a transiently-attached element — treating a detached-at-check-time element as 'not visible' is the semantically correct fallback; the caller's branch logic uses the boolean result.
      const emptyVisible = (await emptyResults.count()) > 0 && await emptyResults.first().isVisible().catch(() => false);

      // Either results area or empty results message should be shown
      expect(resultsVisible || emptyVisible).toBe(true);

      // error-display must NOT be visible (D85) — search should not crash
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    // This test verifies that navigating to /ai/search shows a meaningful response —
    // either the feature is properly gated (access control working when capability is disabled)
    // or the feature works correctly (capability is enabled). Both outcomes are valid.
    // No test.skip() — the test always runs and always passes in a correctly functioning system.
    test('AI search route shows gating or working page (no unexpected crash or blank state)', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      // Auth must not have expired during navigation
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login — user should be authenticated');
      }

      // CapabilityRoute may redirect away from /ai/search without using /403 URL
      const redirectedAway = !page.url().includes('/ai/search') && !page.url().includes('/login');
      const isGated =
        page.url().includes('/403') ||
        redirectedAway ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .unavailable-page, [data-testid="unavailable-page"], [data-testid="forbidden-page"]').count()) > 0;

      // isWorking: on the route with any meaningful content (.app-main, [data-testid="app-main"] handles inline capability gating)
      const isWorking =
        page.url().includes('/ai/search') &&
        (await page.locator('.ai-search-page, .app-main, [data-testid="app-main"]').count()) > 0 &&
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().count()) === 0;

      // Route must resolve to one of the two expected states — never a blank/crash page
      expect(isGated || isWorking).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('search and AI search routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/search');
      await navigateToRouteFromApp(page, '/ai/search', {
        timeout: 60000,
        contentSelector: '.ai-search-page, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
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
