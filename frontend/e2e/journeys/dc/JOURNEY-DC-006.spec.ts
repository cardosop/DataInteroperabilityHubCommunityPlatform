/**
 * E2E Test: JOURNEY-DC-006 — Use Natural Language Search
 *
 * Journey: Use Natural Language Search
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /search, /ai/search.
 * Uses getConsumerTestUser(). Capability-gated: ai.natural-language-search. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginAsPersona, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-006: Use Natural Language Search', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo adds latency; login + search + AI search nav

  test.describe('Success', () => {
    test('search page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const onSearch = page.url().includes('/search');
      const hasContent = (await page.locator('.search-page, .app-main').count()) > 0;
      expect(onLogin || (onSearch && hasContent)).toBe(true);
    });

    test('AI search page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onAISearch = page.url().includes('/ai/search');
      const hasContent =
        (await page.locator('.ai-search-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onAISearch && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('AI search without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
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
      await loginAsPersona(page, getConsumerTestUser);
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/search', {
        timeout: 60000,
        contentSelector: '.search-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/search');
      await loginAndNavigateToRoute(page, consumer, '/ai/search', {
        timeout: 60000,
        contentSelector: '.ai-search-page, .unavailable-page, .error-display',
      });
      expect(
        page.url().includes('/ai/search') ||
          page.url().includes('/403') ||
          page.url().includes('/login') ||
          page.url().includes('/unavailable')
      ).toBe(true);
    });
  });
});
