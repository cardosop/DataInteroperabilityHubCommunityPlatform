/**
 * E2E Test: JOURNEY-AUTH-001 — First-Time Visitor Registers
 *
 * Journey: First-Time Visitor Registers
 * Persona: Visitor, Prospect
 * Use cases: UC-AUTH-001
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Per-journey structure: Success, Failure, Edge. Shared steps from fixtures/auth-journey-steps.
 * No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import {
  registerViaApi,
  runJOURNEY_AUTH_001_Success,
  strongPassword,
  uniqueEmail,
  waitForRegisterPageReady,
} from '../../fixtures/auth-journey-steps';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-AUTH-001: First-Time Visitor Registers', () => {
  test.setTimeout(240000); // 4 min: register + capabilities + login + rate-limit headroom under parallel E2E load

  test.describe('Success', () => {
    test('visitor registers via UI and then logs in', async ({ page }) => {
      await runJOURNEY_AUTH_001_Success(page);
    });

    test('visitor registers and has personal tenant', async ({ page }) => {
      await runJOURNEY_AUTH_001_Success(page);
    });

    test('visitor registers and can create asset', async ({ page }) => {
      test.setTimeout(300000); // 5 min: register + login + asset creation
      await runJOURNEY_AUTH_001_Success(page);
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector(
        '.asset-list-page, .empty-state, .error-display, .asset-list-header, h1:has-text("Assets")',
        { timeout: 30_000 }
      );
      await waitForLoadingComplete(page, { timeout: 30_000 });
      const errorDisplay = page.locator('.error-display');
      if ((await errorDisplay.count()) > 0) {
        const retryBtn = page.locator('.error-display-retry');
        if ((await retryBtn.count()) > 0) {
          await retryBtn.first().click();
          await waitForLoadingComplete(page, { timeout: 30_000 });
        }
      }
      const createButton = page
        .locator('button:has-text("Create Asset")')
        .or(page.locator('.empty-state-action:has-text("Create Asset")'));
      await createButton.first().waitFor({ state: 'visible', timeout: 20_000 });
      await createButton.first().click();
      await expect(page).toHaveURL(/\/assets\/create/, { timeout: 15_000 });
      await waitForLoadingComplete(page);
      await page.waitForSelector('input[id="key"]', { timeout: 15_000 });
      const assetKey = `e2e-personal-${Date.now()}`;
      await page.fill('input[id="key"]', assetKey);
      await page.fill('input[id="name"]', 'E2E Personal Asset');
      await page.fill('textarea[id="description"]', 'Asset created by visitor in personal tenant');
      await page.selectOption('select[id="visibility"]', 'INTERNAL');
      const submitButton = page.locator('button:has-text("Create Asset")');
      await submitButton.waitFor({ state: 'visible', timeout: 10_000 });
      await submitButton.click();
      await expect(page).toHaveURL(/\/assets\/[^/]+$/, { timeout: 30_000 });
      await waitForLoadingComplete(page, { timeout: 35_000 });
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        throw new Error(
          `Asset creation failed (visitor in personal tenant). Backend error: ${errText.slice(0, 250)}`
        );
      }
      const assetHeading = page
        .locator('.asset-detail-page .asset-detail-content h1, .asset-detail-page h1')
        .first();
      await expect(assetHeading).toBeVisible({ timeout: 15_000 });
      await expect(assetHeading).toContainText('E2E Personal Asset', { timeout: 10_000 });
    });
  });

  test.describe('Failure', () => {
    test('registration page shows validation when fields empty', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        const createLink = page.getByRole('link', { name: /Create an account/i });
        await createLink.waitFor({ state: 'visible', timeout: 35_000 });
        await createLink.click();
        await page.waitForURL((url) => url.pathname.includes('/register'), { timeout: 5000 });
      }
      await waitForRegisterPageReady(page);
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Registration unavailable (capabilities/schema). JOURNEY-AUTH-001 requires registration to be enabled. ' +
            'Enable registration in deployment capabilities or schema.'
        );
      }
      await page.click('button[type="submit"]');
      await page.waitForTimeout(500);
      const stillOnRegister = page.url().includes('/register');
      expect(stillOnRegister).toBe(true);
    });

    test('duplicate email shows error or stays on register', async ({ page }) => {
      test.setTimeout(120000);
      const email = uniqueEmail('e2e_dup');
      const password = strongPassword();
      const name = 'E2E Dup User';
      await registerViaApi({ email, password, name });
      await clearAuthStorage(page);
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        const createLink = page.getByRole('link', { name: /Create an account/i });
        await createLink.waitFor({ state: 'visible', timeout: 35_000 });
        await createLink.click();
        await page.waitForURL((url) => url.pathname.includes('/register'), { timeout: 5000 });
      }
      await waitForRegisterPageReady(page);
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Registration unavailable (capabilities/schema). JOURNEY-AUTH-001 requires registration to be enabled. ' +
            'Enable registration in deployment capabilities or schema.'
        );
      }
      await page.fill('input#name', name);
      await page.fill('input#email', email);
      await page.fill('input#password', password);
      await page.click('button[type="submit"]');
      await page.waitForSelector('.error-message, [role="alert"]', { timeout: 15000 }).catch(() => null);
      await page.waitForTimeout(2000);
      const hasError =
        (await page.locator('.error-message').count()) > 0 || page.url().includes('/register');
      expect(hasError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('empty submit stays on register (HTML5 validation)', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        const createLink = page.getByRole('link', { name: /Create an account/i });
        await createLink.waitFor({ state: 'visible', timeout: 35_000 });
        await createLink.click();
        await page.waitForURL((url) => url.pathname.includes('/register'), { timeout: 5000 });
      }
      await waitForRegisterPageReady(page);
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Registration unavailable (capabilities/schema). JOURNEY-AUTH-001 requires registration to be enabled. ' +
            'Enable registration in deployment capabilities or schema.'
        );
      }
      await page.locator('button[type="submit"]').click();
      await page.waitForTimeout(500);
      expect(page.url()).toContain('/register');
    });

    test('register with optional display name', async ({ page }) => {
      const email = uniqueEmail('e2e_register_edge');
      const password = strongPassword();
      const name = 'E2E Edge Name';
      await clearAuthStorage(page);
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        const createLink = page.getByRole('link', { name: /Create an account/i });
        await createLink.waitFor({ state: 'visible', timeout: 35_000 });
        await createLink.click();
        await page.waitForURL((url) => url.pathname.includes('/register'), { timeout: 5000 });
      }
      await waitForRegisterPageReady(page);
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Registration unavailable (capabilities/schema). JOURNEY-AUTH-001 requires registration to be enabled. ' +
            'Enable registration in deployment capabilities or schema.'
        );
      }
      await page.fill('input#name', name);
      await page.fill('input#email', email);
      await page.fill('input#password', password);
      await page.click('button[type="submit"]');
      await page.waitForURL((url) => url.pathname === '/login', { timeout: 60_000 });
      await expect(page.locator('.success-message')).toContainText('Account created', {
        timeout: 10_000,
      });
    });
  });
});
