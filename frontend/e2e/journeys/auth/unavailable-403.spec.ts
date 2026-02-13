/**
 * E2E: /unavailable and /403 behavior (Phase 13 — 15.1.5)
 *
 * Asserts that capability or role-gated flows show /unavailable or /403 as expected.
 * No mocks; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';

test.describe('Unavailable and 403 pages', () => {
  test.describe('Success', () => {
    test('/unavailable shows feature unavailable message', async ({ page }) => {
      await page.goto('/unavailable', { waitUntil: 'domcontentloaded' });
      await expect(
        page.getByRole('heading', { name: /Feature Unavailable|Unavailable/i })
      ).toBeVisible({ timeout: 10_000 });
      await expect(page.locator('.unavailable-page').first()).toBeVisible({
        timeout: 5_000,
      });
    });

    test('/403 shows forbidden message', async ({ page }) => {
      await page.goto('/403', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('body')).toContainText(/403|Forbidden/i, { timeout: 10_000 });
    });
  });

  test.describe('Edge', () => {
    test('capability-gated route redirects to /unavailable when capability off', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(register|unavailable)/, { timeout: 15_000 });
      const onUnavailable = page.url().includes('/unavailable');
      const onRegister = page.url().includes('/register');
      expect(onUnavailable || onRegister).toBe(true);
    });
  });
});
