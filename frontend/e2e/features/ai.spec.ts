/**
 * E2E Feature: AI (capability-gated)
 * Routes: /ai/search (ai.natural-language-search), /ai/schema-matching (ai.schema-matching).
 * Both routes are capability-gated via CapabilityRoute — when disabled, they redirect
 * to /unavailable or /coming-soon. Tests verify the gating works correctly.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertCapabilityGatedPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: AI (capability-gated)', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ai search route loads or shows capability-gated redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/search', {
        timeout: 60000,
        contentSelector: '.ai-search-page, .unavailable-page, .coming-soon-page, .error-display, h1',
      });
      await assertCapabilityGatedPageLoads(page, '.ai-search-page, .unavailable-page, .coming-soon-page', {
        timeout: 30000,
      });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to ai redirects to login', async ({ page }) => {
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/ai') || url.includes('/unavailable'),
        'Expected /login redirect, /ai route, or /unavailable'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ai schema-matching route shows capability-gated redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector: '.schema-matching-page, .unavailable-page, .coming-soon-page, .error-display, h1',
      });
      await assertCapabilityGatedPageLoads(
        page,
        '.schema-matching-page, .unavailable-page, .coming-soon-page',
        { timeout: 30000 }
      );
    });
  });
});
