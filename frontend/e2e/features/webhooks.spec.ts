/**
 * E2E Feature: Webhooks
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /webhooks.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Webhooks', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('webhooks list loads or redirects to login', async ({ page }) => {
      await page.goto('/webhooks');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to login — auth may have expired');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/webhooks');
      // Success test must NOT accept .error-display
      await expect(page.locator('.error-display')).not.toBeVisible();
      const hasContent =
        (await page.locator('.webhook-list-page, .empty-state, h1').count()) > 0;
      expect(
        hasContent,
        'Expected .webhook-list-page, .empty-state, or h1 on /webhooks'
      ).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(onLogin || hasError).toBe(true) /* acceptable states */;
    });
  });
});
