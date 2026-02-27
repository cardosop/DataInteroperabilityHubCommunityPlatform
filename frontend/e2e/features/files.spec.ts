/**
 * E2E Feature: Files
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /files.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Files', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('files list loads or redirects to login', async ({ page }) => {
      await page.goto('/files');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/files');
    });
  });

  test.describe('Edge', () => {
    test('files route responds', async ({ page }) => {
      await page.goto('/files');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      expect(page.url()).toContain('/files');
    });
  });
});
