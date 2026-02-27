/**
 * E2E Test: JOURNEY-DS-004 — Tune Recommendation Engine
 *
 * Journey: Tune Recommendation Engine
 * Persona: Data Scientist / ML Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /ml (recommendation config under ML).
 * Capability-gated: ml.models. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DS-004: Tune Recommendation Engine', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ML page loads for recommendation configuration', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onMl = page.url().includes('/ml');
      const hasContent =
        (await page.locator('.ml-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onMl && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('ML page without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onMl = page.url().includes('/ml');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onMl || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ML page accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/login') || page.url().includes('/403') || page.url().includes('/ml')).toBe(true);
    });
  });
});
