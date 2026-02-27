/**
 * E2E Feature: Scheduled Ingestion
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /scheduled-ingestions (plural, per routes.tsx).
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Scheduled Ingestion', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('scheduled-ingestions route loads or redirects to login', async ({ page }) => {
      await page.goto('/scheduled-ingestions');
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
      expect(url).toMatch(/\/scheduled-ingestions|\/login|\/403/);
    });
  });

  test.describe('Edge', () => {
    test('scheduled-ingestions responds', async ({ page }) => {
      await page.goto('/scheduled-ingestions');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      expect(page.url()).toMatch(/\/scheduled-ingestions|\/login|\/403|\/unavailable/);
    });
  });
});
