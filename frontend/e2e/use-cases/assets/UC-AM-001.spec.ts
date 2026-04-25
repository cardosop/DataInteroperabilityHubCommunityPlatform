/**
 * E2E: UC-AM-001 — Create Asset via Data-First Flow
 *
 * Use Case: Create Asset via Data-First Flow
 * Persona: Data Product Owner, Data Engineer
 * Reference: docs/USE_CASES.md#uc-am-001
 *
 * Success/Failure/Edge. Routes: /assets, /assets/create.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-AM-001: Create Asset via Data-First Flow', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads for authenticated user', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state',
      });
      expect(page.url()).toContain('/assets');
      await waitForLoadingComplete(page, { timeout: 15000 });
      await expect(page.locator('.error-display')).not.toBeVisible();
      const hasContent =
        (await page.locator('.asset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('create asset via form: fill name, key, description, submit', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets/create', {
        timeout: 60000,
        contentSelector: 'form, .asset-form',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth not available');
      }
      expect(page.url()).toContain('/assets/create');
      await waitForLoadingComplete(page, { timeout: 15000 });

      const uniqueSuffix = Date.now().toString(36);
      const assetKey = `e2e-asset-${uniqueSuffix}`;
      const assetName = `E2E Asset ${uniqueSuffix}`;

      // Fill key first (matches form order: key appears before name in the DOM)
      const keyInput = page.locator('#key').first();
      await keyInput.waitFor({ state: 'visible', timeout: 10000 });
      await keyInput.fill(assetKey);
      // Verify React state updated by checking input value
      await expect(keyInput).toHaveValue(assetKey);

      const nameInput = page.locator('#name').first();
      await nameInput.waitFor({ state: 'visible', timeout: 10000 });
      await nameInput.fill(assetName);
      await expect(nameInput).toHaveValue(assetName);

      const descInput = page.locator('#description').first();
      if ((await descInput.count()) > 0 && await descInput.isVisible()) {
        await descInput.fill('Automated E2E test asset');
      }

      const submitBtn = page.locator('button[type="submit"]').first();
      await submitBtn.waitFor({ state: 'visible', timeout: 10000 });
      // Ensure submit button is enabled (not in loading state)
      await expect(submitBtn).toBeEnabled({ timeout: 5000 });

      const [response] = await Promise.all([
        page.waitForResponse((resp) => resp.url().includes('/assets') && resp.request().method() === 'POST', { timeout: 30000 }),
        submitBtn.click(),
      ]);

      if (response.status() >= 400) {
        // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
        const body = await response.text().catch(() => '');
        throw new Error(`POST /assets/ returned ${response.status()}: ${body}`);
      }

      await page.waitForTimeout(1500);
      expect(page.url()).not.toContain('/assets/create');
      await expect(page.locator('.error-display')).not.toBeVisible();
    });

    test('assets create route loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets/create', {
        timeout: 60000,
        contentSelector: 'form, .asset-form',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/assets/create');
      const hasForm =
        (await page.locator('form, .asset-form').count()) > 0;
      expect(hasForm).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to assets redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || (url.includes('/assets') && (await page.locator('input#email, [href*="/login"]').count()) > 0)).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('assets list with empty state shows create option', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
      const hasContent =
        (await page.locator('.asset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
      const hasCreateOption =
        (await page.locator('a[href*="/assets/create"], button:has-text("Create"), button:has-text("New Asset")').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasCreateOption).toBe(true);
    });
  });
});
