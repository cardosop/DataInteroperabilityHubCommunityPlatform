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

test.describe('JOURNEY-AUTH-001: First-Time Visitor Registers', () => {
  test.setTimeout(120000); // 2 min: register + login may need capabilities load and rate-limit headroom

  test.describe('Success', () => {
    test('visitor registers via UI and then logs in', async ({ page }) => {
      await runJOURNEY_AUTH_001_Success(page);
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
      await page.waitForTimeout(3000);
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
      await page.waitForURL((url) => url.pathname === '/login', { timeout: 20_000 });
      await expect(page.locator('.success-message')).toContainText('Account created', {
        timeout: 10_000,
      });
    });
  });
});
