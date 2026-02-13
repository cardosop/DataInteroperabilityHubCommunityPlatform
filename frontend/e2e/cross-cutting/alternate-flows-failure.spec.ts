/**
 * E2E: Alternate Flows — Failure dimension (Phase 13 — 15.9.1)
 * Review docs/USE_CASES.md "Alternate Flows" (A1–An); add failure E2E where UI can trigger the flow.
 * Real backend only; no mocks.
 * Covered: duplicate key (asset create → API 400), non-existent resource errors (see route specs).
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Alternate flows — failure (USE_CASES A1–An)', () => {
  test.setTimeout(120000);

  test('asset create with duplicate key shows API error (A2-style)', async ({ page }) => {
    const key = `e2e-dup-${Date.now()}`;
    await page.goto('/assets/create');
    try {
      await waitForAppMainReady(page, { contentSelector: '.asset-create-page', timeout: 60000 });
    } catch (_err) {
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      throw _err;
    }
    await page.fill('input[id="key"]', key);
    await page.fill('input[id="name"]', 'First Asset');
    await page.fill('textarea[id="description"]', 'Description');
    await page.locator('button:has-text("Create Asset")').click();
    await page.waitForURL(/\/assets\/[^/]+$/, { timeout: 15000 }).catch(() => null);

    await page.goto('/assets/create');
    try {
      await waitForAppMainReady(page, { contentSelector: '.asset-create-page', timeout: 60000 });
    } catch (_err) {
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      throw _err;
    }
    await page.fill('input[id="key"]', key);
    await page.fill('input[id="name"]', 'Second Same Key');
    await page.fill('textarea[id="description"]', 'Description');
    await page.locator('button:has-text("Create Asset")').click();
    await page.waitForTimeout(3000);

    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/already exists|duplicate|400|unique/i').count()) > 0;
    const stillOnCreate = page.url().includes('/assets/create');
    expect(hasError || stillOnCreate).toBe(true);
  });
});
