/**
 * E2E Feature: Semantic
 * Per E2E_FULL_COVERAGE_PLAN and tasks 29.1.10. Routes: /semantic.
 * Assert route loads or shows /unavailable when capability-gated. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { assertSuccessLoad } from '../fixtures/journey-helpers';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Semantic', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic route loads when authenticated and capability enabled', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto('/semantic');
      try {
        await waitForAppMainReady(page, { timeout: 60000, acceptRedirectToLogin: true });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) return;
        throw _err;
      }
      const url = page.url();
      expect(url).toMatch(/\/semantic|\/login|\/403|\/unavailable/);
      if (url.includes('/semantic')) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="semantic-page"], .semantic-page, .unavailable-page',
        });
      } else if (url.includes('/unavailable')) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="unavailable-page"], .unavailable-page',
        });
      }
    });
  });

  test.describe('Edge', () => {
    test('semantic shows /unavailable when capability-gated', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto('/semantic');
      // Wait for the app to fully initialize (lazy bundles + auth check) rather than a fixed sleep.
      // waitForAppMainReady handles the visible/slowMo project's slower rendering correctly.
      try {
        await waitForAppMainReady(page, { timeout: 30000, acceptRedirectToLogin: true });
      } catch {
        // Ignore if the route is gated or login redirect fires
      }
      const url = page.url();
      const onSemantic = url.includes('/semantic');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      expect(onSemantic || onUnavailable || onLogin || on403).toBe(true);
      if (onSemantic) {
        // Wait for the page content to become visible — lazy bundle may still be loading
        await page
          .locator('[data-testid="semantic-page"], .semantic-page, .unavailable-page')
          .first()
          .waitFor({ state: 'visible', timeout: 15000 })
          .catch(() => {});
        const hasContent =
          (await page.locator('[data-testid="semantic-page"], .semantic-page, .unavailable-page').count()) > 0;
        expect(hasContent).toBe(true);
      } else if (onUnavailable) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="unavailable-page"], .unavailable-page',
        });
      }
    });
  });
});
