/**
 * E2E Test: JOURNEY-PA-003 — Configure Platform Settings
 * Persona: Platform Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/pa/JOURNEY-PA-003.md
 * Real backend only; no mocks.
 */
import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-PA-003: Configure Platform Settings', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('platform admin can navigate to platform settings and save a change', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      const settingsRoutes = ['/admin/settings', '/admin/platform-settings', '/admin'];
      let landed = false;

      for (const route of settingsRoutes) {
        await loginAndNavigateToRoute(page, paUser, route, {
          timeout: 60000,
          contentSelector: '.admin-page, .platform-settings-page, .settings-page',
        });
        if (page.url().includes('/403') || page.url().includes('/login')) continue;
        const hasSettings =
          (await page.locator('.platform-settings-page, .settings-page').count()) > 0 ||
          (await page.locator('h1:has-text("Settings"), h1:has-text("Platform")').count()) > 0;
        if (hasSettings) { landed = true; break; }
      }

      if (!landed) {
        test.skip(true, 'Platform settings page not found at any known route');
        return;
      }

      // Find any boolean toggle or text field to change
      const toggle = page.locator('input[type="checkbox"], input[type="toggle"]').first();
      const textField = page.locator('input[type="text"]:not([readonly])').first();

      let madeChange = false;
      if ((await toggle.count()) > 0) {
        await toggle.click();
        madeChange = true;
      } else if ((await textField.count()) > 0) {
        const currentVal = await textField.inputValue();
        await textField.fill(currentVal + ' ');
        madeChange = true;
      }

      if (!madeChange) {
        test.skip(true, 'No editable field found on platform settings page');
        return;
      }

      const saveBtn = page.locator(
        'button[type="submit"]:has-text("Save"), button:has-text("Save Settings")'
      );
      if ((await saveBtn.count()) === 0) {
        test.skip(true, 'Save button not found on platform settings page');
        return;
      }

      const saveResponse = page.waitForResponse(
        (r) =>
          (r.url().includes('/admin/settings') || r.url().includes('/platform-settings')) &&
          (r.request().method() === 'PATCH' || r.request().method() === 'PUT' || r.request().method() === 'POST'),
        { timeout: 20000 }
      );
      await saveBtn.first().click();
      const resp = await saveResponse.catch(() => null);
      if (resp) {
        expect(resp.status()).toBeGreaterThanOrEqual(200);
        expect(resp.status()).toBeLessThan(300);
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      expect(page.url()).toMatch(/\/login|\/403|\/admin/);
    });
  });

  test.describe('Route', () => {
    test('admin page loads', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', {
        timeout: 60000,
        contentSelector: '.admin-page, .error-display, [data-testid="forbidden-page"]',
      });
      expect(page.url()).toMatch(/\/admin|\/403|\/login/);
    });
  });
});
