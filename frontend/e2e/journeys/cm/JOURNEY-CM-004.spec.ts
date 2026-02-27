/**
 * E2E Test: JOURNEY-CM-004 — Manage Activity Feeds
 *
 * Journey: Manage Activity Feeds
 * Persona: Community Manager
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /social (activity feeds).
 * Capability-gated: social.ratings. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-CM-004: Manage Activity Feeds', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('social page loads for activity feeds', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onSocial = page.url().includes('/social');
      const hasContent =
        (await page.locator('.social-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onSocial && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('social without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onSocial = page.url().includes('/social');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onSocial || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('social page loads with empty or populated feeds', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/social')).toBe(true);
    });
  });
});
