/**
 * E2E Test: JOURNEY-AUTH-004 — Unauthenticated User Accesses Public Resources
 *
 * Journey: Unauthenticated User Accesses Public Resources
 * Persona: Visitor
 * Use cases: UC-AUTH-004
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Per-journey structure: Success, Failure, Edge. Shared steps from fixtures/auth-journey-steps.
 * No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import { runJOURNEY_AUTH_004_Success } from '../../fixtures/auth-journey-steps';

test.describe('JOURNEY-AUTH-004: Unauthenticated User Accesses Public Resources', () => {
  test.describe('Success', () => {
    test('unauthenticated user can access public resources page', async ({ page }) => {
      await runJOURNEY_AUTH_004_Success(page);
    });
  });

  test.describe('Failure', () => {
    test('public page does not redirect to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/public', { waitUntil: 'domcontentloaded' });
      expect(page.url()).toContain('/public');
      expect(page.url()).not.toContain('/login');
    });

    test('unauthenticated access to protected route redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onAssetsWithLoginPrompt =
        url.includes('/assets') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onAssetsWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('public page shows OpenAPI link', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/public', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('a').filter({ hasText: 'OpenAPI' }).first()).toBeVisible({
        timeout: 10_000,
      });
    });

    test('unauthenticated user visiting protected route sees no authenticated content', async ({
      page,
    }) => {
      // Verify that protected content (.app-sidebar, user-specific data) is NOT rendered —
      // distinct from the Failure test which only checks the URL redirect target.
      await clearAuthStorage(page);
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets)/, { timeout: 20_000 });
      // Authenticated shell must not be visible to unauthenticated visitors
      const appSidebar = page.locator('.app-sidebar');
      const appHeader = page.locator('.app-header');
      const sidebarVisible = await appSidebar.isVisible().catch(() => false);
      const headerVisible = await appHeader.isVisible().catch(() => false);
      // When redirected to /login the shell is not rendered; when on /assets the shell should
      // also not render because auth guard clears it before login prompt is shown.
      const url = page.url();
      if (url.includes('/login')) {
        expect(sidebarVisible).toBe(false);
      } else {
        // Still on /assets with a login prompt embedded — authenticated shell should not exist
        expect(sidebarVisible || headerVisible).toBe(false);
      }
    });
  });
});
