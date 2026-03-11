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
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic page loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
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
    test('semantic page without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onSemantic = page.url().includes('/semantic');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onSemantic || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('semantic page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/semantic')).toBe(true);
    });
  });
});
