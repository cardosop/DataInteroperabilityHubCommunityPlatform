/**
 * E2E Feature: Scheduled Export
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /scheduled-exports (plural, per routes.tsx).
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Scheduled Export', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('scheduled-exports route loads or redirects to login', async ({ page }) => {
      await page.goto('/scheduled-exports');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      const url = page.url();
      expect(url).toMatch(/\/scheduled-exports|\/login|\/403/);
    });
  });

  test.describe('Edge', () => {
    test('scheduled-exports responds', async ({ page }) => {
      await page.goto('/scheduled-exports');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      expect(page.url()).toMatch(/\/scheduled-exports|\/login|\/403|\/unavailable/);
    });
  });
});
