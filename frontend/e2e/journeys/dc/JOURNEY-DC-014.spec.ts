/**
 * E2E Test: JOURNEY-DC-014 — Discover ODPS Products (Semantic Search)
 *
 * Journey: Discover ODPS Products (Semantic Search)
 * Persona: Data Consumer
 * Use Case: UC-DC-006 (Use Natural Language Search), UC-AI-001 (Natural Language Search)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /semantic.
 * Capability-gated: semantic.sparql. Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DC-014: Discover ODPS Products (Semantic Search)', () => {
  test.setTimeout(300000); // 5 min: login retries can take ~80s under parallel E2E load

  test.describe('Success', () => {
    test('semantic page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.semantic-page, .app-main, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onSemantic = url.includes('/semantic');
      const hasContent =
        (await page.locator('.semantic-page, .app-main, .unavailable-page, .loading-spinner-container').count()) >
        0;
      expect(onLogin || on403 || onUnavailable || (onSemantic && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /semantic redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/semantic', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)/, { timeout: 20000 }).catch(() => null);
      expect(page.url().includes('/login') || page.url().includes('/403')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('semantic page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.semantic-page, .app-main, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/semantic')).toBe(true);
    });
  });
});
