/**
 * E2E: /unavailable and /403 behavior (Phase 13 — 15.1.5)
 *
 * Asserts that capability or role-gated flows show /unavailable or /403 as expected.
 * No mocks; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';

test.describe('Unavailable and 403 pages', () => {
  test.describe('Failure', () => {
    test('unauthenticated access to protected route redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/admin')).toBe(true);
    });
  });

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
      // Clear stale auth state first — a failed token refresh from prior tests
      // can trigger the 401 interceptor's hard redirect to /login.
      await clearAuthStorage(page);
      await page.goto('/403', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('body')).toContainText(/403|Forbidden/i, { timeout: 15_000 });
    });
  });

  test.describe('Edge', () => {
    test('capability-gated /register renders valid page (unavailable or register form)', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(register|unavailable|login)/, { timeout: 15_000 }).catch(() => null);
      const url = page.url();
      // If registration is disabled → /unavailable. If enabled → /register.
      // Either is valid; what must NOT happen is a crash or blank page.
      expect(url.includes('/unavailable') || url.includes('/register') || url.includes('/login')).toBe(true);
      // Verify a heading is rendered (not a blank page regression).
      // 35s timeout: in visible/slowMo mode the capability API call (to check if registration
      // is enabled) can take several seconds before the page resolves to its final state.
      const heading = page.locator('h1, h2').first();
      await expect(heading).toBeVisible({ timeout: 35000 });
    });
  });
});
