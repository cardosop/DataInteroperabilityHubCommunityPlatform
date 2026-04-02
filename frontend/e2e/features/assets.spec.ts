/**
 * E2E Feature: Assets
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /assets, /assets/create, /assets/:id.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Assets', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads (or redirects to login)', async ({ page }) => {
      await page.goto('/assets');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector: '.asset-list-page, .empty-state',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/assets');
    });
  });

  test.describe('Failure', () => {
    test('asset detail with non-existent id shows error or redirect', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/assets/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const hasError = (await page.locator('.error-display').count()) > 0;
      // `noDetail` was trivially true after any redirect (page doesn't have .asset-detail-page
      // when redirected to login or when not yet loaded). Removed — only assert real error signals.
      expect(
        onLogin || hasError,
        'Expected .error-display or login redirect for a nil-UUID asset detail'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('assets create route loads or requires auth', async ({ page }) => {
      await page.goto('/assets/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const onCreate = page.url().includes('/assets/create');
      const hasForm =
        (await page.locator('form').count()) > 0 || (await page.locator('.asset-form').count()) > 0;
      // `onCreate` alone was trivially true (we navigated there and staying counts as a pass).
      // If on create route, must also show a form — otherwise the route rendered something broken.
      if (onLogin) {
        expect(onLogin).toBe(true);
        return;
      }
      expect(
        onCreate && hasForm,
        'Expected a form (.asset-form or <form>) to be present when on /assets/create'
      ).toBe(true);
    });
  });
});
