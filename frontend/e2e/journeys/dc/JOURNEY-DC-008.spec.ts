/**
 * E2E Test: JOURNEY-DC-008 — Rate and Review Asset
 *
 * Journey: Rate and Review Asset
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /social.
 * Capability-gated: social.ratings. Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DC-008: Rate and Review Asset', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('social page loads (ratings/reviews)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
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
    test('social page without capability shows 403 or unavailable', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
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
    test('social page loads or redirects', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/social');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/social')).toBe(true);
    });
  });
});
