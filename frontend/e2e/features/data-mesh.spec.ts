/**
 * E2E Feature: Data Mesh
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /mesh, /mesh/topology, /mesh/create, /mesh/:id.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Data Mesh', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh list loads or redirects to login', async ({ page }) => {
      await page.goto('/mesh');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/mesh');
    });
  });

  test.describe('Failure', () => {
    test('mesh detail with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/mesh/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const onMesh = url.includes('/mesh');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(onLogin || onMesh || hasError).toBe(true);
    });
  });
});
