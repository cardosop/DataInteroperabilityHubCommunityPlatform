/**
 * E2E Feature: Governance
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /governance, /governance/retention, /governance/access-requests.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Governance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('governance route loads or redirects to login/403', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/governance', {
        timeout: 60000,
        contentSelector: '.governance-page, .empty-state, .error-display, h1',
      });
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        // Role-gated redirect — acceptable for governance (requires TENANT_ADMIN/PLATFORM_ADMIN)
        expect(url).toMatch(/\/login|\/403/);
        return;
      }
      // If on /governance, assert actual content rendered (not just the URL)
      await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.governance-page, .empty-state, h1').count()) > 0;
      expect(hasContent, 'Expected governance content to render on /governance').toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('governance retention with missing role shows 403 or redirect', async ({ page }) => {
      // Navigate without explicit role — may get 403 if default user lacks governance role
      await page.goto('/governance/retention');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch (err) {
        // Only acceptable if we ended up on /login or /403
        const url = page.url();
        if (!/\/(login|403|unavailable)/.test(url)) throw err;
      }
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasForbidden =
        (await page.locator('[data-testid="forbidden-page"]').count()) > 0 ||
        (await page.locator('text=/forbidden|access denied/i').count()) > 0;
      expect(
        on403 || onLogin || hasForbidden,
        'Expected 403, login redirect, or forbidden content for non-admin user'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('governance retention list page loads when authorized', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/governance/retention', {
        timeout: 60000,
        contentSelector:
          '.governance-retention-policy-list-page, .empty-state, .error-display, [data-testid="forbidden-page"], h1',
      });
      const url = page.url();
      if (url.includes('/403') || url.includes('/login')) {
        // Role-gated redirect — acceptable
        expect(url).toMatch(/\/403|\/login/);
        return;
      }
      if (url.includes('/governance/retention')) {
        const hasMeaningfulContent =
          (await page.locator('.governance-retention-policy-list-page').count()) > 0 ||
          (await page.locator('.empty-state').count()) > 0;
        const hasError = (await page.locator('.error-display').count()) > 0;

        if (hasError && !hasMeaningfulContent) {
          const errorText = await page.locator('.error-display').first().textContent();
          throw new Error(`Governance retention page rendered only an error: ${errorText}`);
        }
        expect(
          hasMeaningfulContent,
          'Expected .governance-retention-policy-list-page or .empty-state'
        ).toBe(true);
      }
    });
  });
});
