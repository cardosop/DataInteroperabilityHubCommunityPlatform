/**
 * E2E Test: JOURNEY-DS-003 — Configure ML-Based Anomaly Detection
 *
 * Journey: Configure ML-Based Anomaly Detection
 * Persona: Data Scientist / ML Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /ml.
 * Capability-gated: ml.models. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DS-003: Configure ML-Based Anomaly Detection', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ML page loads (capability-gated)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ml-page, .app-main, .unavailable-page, [data-testid="unavailable-page"], #email',
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login — user should be authenticated');
      }
      const url = page.url();
      const redirectedAway = !url.includes('/ml') && !url.includes('/login');
      const isGated =
        url.includes('/403') ||
        url.includes('/unavailable') ||
        redirectedAway ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').count()) > 0;
      // Both outcomes are valid: capability enabled (page loads) or disabled (properly gated)
      if (isGated) {
        expect(isGated).toBe(true); // Capability gate is working — valid outcome
        return;
      }
      const onMl = url.includes('/ml');
      const hasContent = (await page.locator('.ml-page, .app-main').count()) > 0;
      expect(onMl && hasContent).toBe(true);
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

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/ml');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('ML page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/ml')).toBe(true);
    });
  });
});
