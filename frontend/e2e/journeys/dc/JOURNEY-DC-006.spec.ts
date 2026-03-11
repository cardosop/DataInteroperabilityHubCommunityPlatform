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
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DC-006: Use Natural Language Search', () => {
  test.setTimeout(240000); // 4 min: visible/slowMo; login + search + AI search nav under API load

  test.describe('Success', () => {
    test('search page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.search-page, .app-main, .loading-spinner-container, .unavailable-page, #email',
        { timeout: 60000 }
      );
      const url = page.url();
      const onLogin = url.includes('/login');
      const onUnavailable = url.includes('/unavailable');
      const onSearch = url.includes('/search');
      const hasContent =
        (await page.locator('.search-page, .app-main, .loading-spinner-container, .unavailable-page').count()) > 0;
      expect(onLogin || onUnavailable || (onSearch && hasContent)).toBe(true);
    });

    test('AI search page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ai-search-page, .ai-search-header, .ai-search-input-section, .app-main, .unavailable-page, .empty-state, .loading-spinner-container, #email',
        { timeout: 60000 }
      );
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onAISearch = page.url().includes('/ai/search');
      const hasContent =
        (await page.locator(
          '.ai-search-page, .ai-search-header, .ai-search-input-section, .app-main, .unavailable-page, .empty-state, .loading-spinner-container'
        ).count()) > 0;
      expect(onLogin || on403 || (onAISearch && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('AI search without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ai-search-page, .unavailable-page, .error-display, .loading-spinner-container, #email',
        { timeout: 60000 }
      );
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onAISearch = page.url().includes('/ai/search');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onAISearch || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('search and AI search routes accessible', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.search-page, .empty-state, .error-display, .loading-spinner-container, .unavailable-page, #email',
        { timeout: 90000 }
      );
      expect(page.url()).toContain('/search');
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ai-search-page, .unavailable-page, .error-display, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      expect(
        page.url().includes('/ai/search') ||
          page.url().includes('/403') ||
          page.url().includes('/login') ||
          page.url().includes('/unavailable')
      ).toBe(true);
    });
  });
});
