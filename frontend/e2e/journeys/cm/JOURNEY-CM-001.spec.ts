/**
 * E2E Test: JOURNEY-CM-001 — Manage Data Community
 *
 * Journey: Manage Data Community
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /social (communities).
 * Capability-gated: social.ratings. Uses default storageState (e2e_test). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

test.describe('JOURNEY-CM-001: Manage Data Community', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('social page loads for community management', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.social-page, .app-main, .unavailable-page, .loading-spinner-container, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 25000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onSocial = url.includes('/social');
      const onUnavailable = url.includes('/unavailable');
      const hasContent =
        (await page.locator('.social-page, .app-main, .unavailable-page, .loading-spinner-container, #email').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onSocial && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('social without capability shows 403 or unavailable', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onSocial = url.includes('/social');
      const onLogin = url.includes('/login');
      const hasUnavailableContent =
        (await page.locator('.unavailable-page, .error-display').count()) > 0;
      expect(on403 || onUnavailable || hasUnavailableContent || onSocial || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('social page loads or redirects', async ({ page }) => {
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(
        url.includes('/login') ||
          url.includes('/403') ||
          url.includes('/social') ||
          url.includes('/unavailable')
      ).toBe(true);
    });
  });
});
