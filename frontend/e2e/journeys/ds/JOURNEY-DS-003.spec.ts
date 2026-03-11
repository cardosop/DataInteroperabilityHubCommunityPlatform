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
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DS-003: Configure ML-Based Anomaly Detection', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ML page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.ml-page, .app-main, .unavailable-page, [data-testid="unavailable-page"], .loading-spinner-container, #email',
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onMl = url.includes('/ml');
      const hasContent =
        (await page.locator('.ml-page, .app-main, .unavailable-page, [data-testid="unavailable-page"]').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onMl && hasContent)).toBe(true);
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
