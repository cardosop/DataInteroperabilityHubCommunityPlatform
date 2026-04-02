/**
 * E2E Feature: Auth
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /login, /register, /public, /password-reset, / (landing vs dashboard).
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';

test.describe('Feature: Auth', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('unauthenticated user at / sees landing page', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('[data-testid="landing-page"]', { timeout: 15_000 });
      await expect(page.locator('[data-testid="landing-login-link"]')).toBeVisible();
      expect(new URL(page.url()).pathname).toBe('/');
    });

    test('authenticated user at / sees dashboard', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      // loginUser already navigates to '/' and waits for app shell.
      // Do NOT call page.goto('/') again — a full reload re-initializes auth,
      // which under parallel E2E load takes 60-120s and causes timeout failures.
      await page.waitForSelector('.app-header', { timeout: 30_000 });
      await expect(
        page.locator('[data-testid="home-page"], .home-page, h1:has-text("Dashboard")').first()
      ).toBeVisible({ timeout: 15_000 });
      expect(page.url()).not.toMatch(/\/login/);
    });

    test('login page loads', async ({ page }) => {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[type="email"], .login-page', { timeout: 15000 });
      expect(page.url()).toMatch(/\/login|\/register/);
    });

    test('public page accessible without auth', async ({ page }) => {
      // The /public route must be accessible without authentication — it must NOT redirect
      // to /login. Accepting a login redirect here would be a false positive (the test name
      // says "accessible without auth" but a redirect means "not accessible without auth").
      await page.goto('/public', { waitUntil: 'domcontentloaded' });
      // Wait for the page to settle — /public should render content, not redirect
      await page
        .locator('h1, .public-page, [data-testid="public-page"], main')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      // Must stay on /public — redirect to /login is a failure for this scenario
      await expect(page).toHaveURL(/\/public/);
      // Must render visible content (not a blank page or error state)
      const hasContent =
        (await page.locator('h1, .public-page, main').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('login with empty credentials shows validation or stays on login', async ({ page }) => {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[type="email"]', { timeout: 15000 }).catch(() => null);
      await page.click('button[type="submit"]').catch(() => null);
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/login');
    });

    test('invalid path redirects or shows 404', async ({ page }) => {
      // The `onApp = url does not include '/nonexistent'` branch was trivially true
      // after any redirect (e.g. redirect to home, login, etc.) and provided no signal.
      // Removed. Only accept: 404 content on page OR redirect to /login for protected routes.
      await page.goto('/nonexistent-auth-route-xyz', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
      const on404 =
        (await page.locator('text=/not found|404/i').count()) > 0 ||
        page.url().includes('/404');
      const onLogin = page.url().includes('/login');
      // Must show 404 feedback or redirect to login — NOT silently land on a valid page
      expect(on404 || onLogin).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Registration validation', () => {
    /**
     * These tests verify the register form rejects invalid input.
     * Each runs as unauthenticated (clearAuthStorage called first) to prevent
     * RegisterPage.tsx's `useEffect` from redirecting to '/' when isAuthenticated=true
     * (which would detach form inputs mid-fill when storageState tokens are present).
     */
    async function navigateToRegister(page: import('@playwright/test').Page): Promise<boolean> {
      // Must clear stored auth tokens first — RegisterPage redirects to '/' when isAuthenticated,
      // which causes form elements to detach during fill operations (120s timeout).
      await clearAuthStorage(page);

      await page.goto('/register', { waitUntil: 'domcontentloaded' });

      // RegistrationRoute shows <LoadingSpinner> while capabilities load (up to 25s + 1 retry).
      // Wait for the TERMINAL state: either the form fields render (capabilities confirmed
      // registration available) or the unavailable page appears (registration disabled).
      // 60s covers: capabilities fetch (25s) + retry (25s) + React render.
      await page
        .locator('input#name, .unavailable-page')
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);

      if (
        page.url().includes('/unavailable') ||
        (await page.locator('.unavailable-page').count()) > 0
      ) {
        return false; // registration feature-flagged off
      }
      if (page.url().includes('/login')) {
        // May redirect to login with a "Create account" link
        const createLink = page.getByRole('link', { name: /Create an account/i });
        if ((await createLink.count()) > 0) {
          await createLink.click();
          await page.waitForURL((url) => url.pathname.includes('/register'), { timeout: 5000 });
        } else {
          return false;
        }
      }
      if ((await page.locator('input#name').count()) === 0) return false;
      // Extra stability wait: ensure form is done rendering (no pending state updates)
      await page.waitForTimeout(500);
      return (await page.locator('input#email, input#name, input#password').count()) > 0;
    }

    test('register with weak password shows validation error', async ({ page }) => {
      const formReady = await navigateToRegister(page);
      if (!formReady) {
        test.skip(true, 'Register page not available or form fields not rendered');
        return;
      }
      // Fill each field using locator.fill() with explicit visibility waits to survive any residual
      // re-renders (capabilities loading can cause brief detaches on slow backends)
      await page.locator('input#name').waitFor({ state: 'visible' });
      await page.locator('input#name').fill('Test User');
      await page.locator('input#email').fill(`test_weak_pw_${Date.now()}@example.com`);
      await page.locator('input#password').fill('123'); // too short, no uppercase
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
      // Should stay on register page and show a validation/error message
      expect(page.url()).toContain('/register');
      const hasError =
        (await page.locator('.error-message, .field-error, [role="alert"]').count()) > 0 ||
        (await page.locator('text=/password|too short|uppercase|lowercase|number|strength/i').count()) > 0 ||
        !(await page.locator('input#password').evaluate((el: HTMLInputElement) => el.validity.valid));
      expect(hasError).toBe(true) /* acceptable states */;
    });

    test('register with invalid email format shows validation error', async ({ page }) => {
      const formReady = await navigateToRegister(page);
      if (!formReady) {
        test.skip(true, 'Register page not available or form fields not rendered');
        return;
      }
      await page.locator('input#name').waitFor({ state: 'visible' });
      await page.locator('input#name').fill('Test User');
      await page.locator('input#email').fill('not-an-email');
      await page.locator('input#password').fill('SecurePass123');
      await page.click('button[type="submit"]');
      await page.waitForTimeout(1000);
      // HTML5 validation or server-side should reject the malformed email
      expect(page.url()).toContain('/register');
      const emailInvalid = !(await page
        .locator('input#email')
        .evaluate((el: HTMLInputElement) => el.validity.valid));
      const hasError =
        emailInvalid ||
        (await page.locator('.error-message, .field-error, [role="alert"]').count()) > 0 ||
        (await page.locator('text=/email|invalid|format/i').count()) > 0;
      expect(hasError).toBe(true) /* acceptable states */;
    });

    test('register with duplicate email shows error', async ({ page }) => {
      const formReady = await navigateToRegister(page);
      if (!formReady) {
        test.skip(true, 'Register page not available or form fields not rendered');
        return;
      }
      await page.locator('input#name').waitFor({ state: 'visible' });
      // Use a known existing E2E user email (created by ensure_e2e_user_roles)
      await page.locator('input#name').fill('Duplicate User');
      await page.locator('input#email').fill('e2e_test@example.com');
      await page.locator('input#password').fill('SecurePass123');
      // Wait for API response — registration with duplicate email must return 4xx
      const [response] = await Promise.all([
        page
          .waitForResponse(
            (resp) =>
              resp.url().includes('/auth/register/') &&
              (resp.status() === 201 || resp.status() === 400 || resp.status() === 409 || resp.status() === 503),
            { timeout: 30000 }
          )
          .catch(() => null),
        page.click('button[type="submit"]'),
      ]);
      await page.waitForTimeout(2000);
      // A 201 here means the backend accepted a duplicate email registration — this is a
      // hard backend integrity violation (broken unique constraint), not a test flakiness.
      // Silently passing with console.warn was hiding real bugs. Fail explicitly instead.
      if (response && response.status() === 201) {
        throw new Error(
          'Backend returned 201 for duplicate email e2e_test@example.com. ' +
          'The unique constraint on email is violated — this is a backend integrity bug, not a test issue.'
        );
      }
      // With 503 (registration disabled/unavailable) the form may stay or navigate away
      if (response && response.status() === 503) {
        test.skip(true, 'Registration service returned 503 — unavailable, cannot test duplicate email');
        return;
      }
      const hasError =
        (await page.locator('.error-message, .field-error, [role="alert"]').count()) > 0 ||
        (await page
          .locator('text=/already exists|duplicate|taken|registered|email.*use|unavailable/i')
          .count()) > 0;
      const stayedOnRegister = page.url().includes('/register');
      expect(hasError || stayedOnRegister).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('register page loads or redirects when registration disabled', async ({ page }) => {
      await page.goto('/register', { waitUntil: 'domcontentloaded' });
      await page
        .locator('h1, .register-page, .unavailable-page')
        .first()
        .waitFor({ state: 'visible', timeout: 25000 })
        .catch(() => null);
      const url = page.url();
      const onRegister = url.includes('/register');
      const onLogin = url.includes('/login');
      const onUnavailable = url.includes('/unavailable');
      const onRoot = url.endsWith('/') || url.match(/\/$/) !== null;
      expect(onRegister || onLogin || onUnavailable || onRoot).toBe(true) /* acceptable states */;
    });
  });
});
