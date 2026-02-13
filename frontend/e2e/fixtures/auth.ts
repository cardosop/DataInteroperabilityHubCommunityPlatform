/**
 * Auth Test Fixtures
 * Helper functions for authentication in E2E tests
 */

import { Page, expect } from '@playwright/test';
import { ensureConsumerTestUser, ensureTestUser, type TestUser } from '../setup/create-test-user';

export type { TestUser };

/**
 * Clear auth state so the page behaves as unauthenticated.
 * Use before auth journey tests that need to see login/register/public/password-reset pages
 * when running with chromium-routes (stored session).
 */
export async function clearAuthStorage(page: Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'domcontentloaded' }).catch(() => null);
  await page.evaluate(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    localStorage.removeItem('refresh_token');
    sessionStorage.clear();
  });
  await page.context().clearCookies();
}

/**
 * Get test user (creates if needed)
 */
export async function getTestUser(): Promise<TestUser> {
  return await ensureTestUser();
}

/**
 * Get consumer test user (creates if needed) - different tenant for purchasing
 */
export async function getConsumerTestUser(): Promise<TestUser> {
  return await ensureConsumerTestUser();
}

/**
 * Login user via UI
 */
export async function loginUser(page: Page, user: TestUser): Promise<void> {
  // Capture console errors
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log(`Browser console error: ${msg.text()}`);
    }
  });

  // Navigate to login page
  await page.goto('/login', { waitUntil: 'domcontentloaded' });

  // Wait for React to hydrate - first wait for the h1 (like login-app-shell test)
  try {
    await page.waitForSelector('h1', { timeout: 10000 });
    await expect(page.locator('h1')).toContainText('Data Interoperability Hub', { timeout: 5000 });
  } catch (e) {
    // If h1 not found, wait a bit more and check what's on the page
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent('body');
    console.log('Page body (first 500 chars):', bodyText?.substring(0, 500));
    throw new Error(`Login page h1 not found. Page content: ${bodyText?.substring(0, 200)}`);
  }

  // Wait for login form to be visible - try both ID and type selectors
  await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
  await page.waitForSelector('input#password, input[type="password"]', { timeout: 10000 });
  await page.waitForSelector('button[type="submit"], button.login-button', { timeout: 10000 });

  // Fill login form - prefer ID selectors
  const emailInput = page.locator('input#email').or(page.locator('input[type="email"]'));
  const passwordInput = page.locator('input#password').or(page.locator('input[type="password"]'));
  await emailInput.fill(user.email);
  await passwordInput.fill(user.password);

  // Wait for button to be enabled (in case it's disabled during loading)
  const submitButton = page
    .locator('button[type="submit"]')
    .or(page.locator('button.login-button'));
  await submitButton.waitFor({ state: 'visible', timeout: 5000 });

  // Submit form and wait for login API response (30s for Docker API)
  // On 429 (rate limit), retry with backoff so E2E suite can complete without flake
  const attemptLogin = async (): Promise<{ status: number; body: string }> => {
    const responsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes('/auth/login/') && (resp.status() === 200 || resp.status() === 429),
      { timeout: 30000 }
    );
    await submitButton.click();
    const resp = await responsePromise;
    const body = await resp.text().catch(() => '');
    return { status: resp.status(), body };
  };

  let loginResponse = await attemptLogin();
  // Auth rate limit is 5/min; wait 65s so the 1-min window resets before retry
  for (let retries = 0; retries < 3 && loginResponse.status === 429; retries++) {
    await page.waitForTimeout(65000);
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
    await emailInput.fill(user.email);
    await passwordInput.fill(user.password);
    loginResponse = await attemptLogin();
  }
  if (loginResponse.status !== 200) {
    throw new Error(`Login API failed with status ${loginResponse.status}: ${loginResponse.body}`);
  }

  // Wait for navigation away from login page (use expect().toHaveURL for better error messages)
  try {
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 });
  } catch (error) {
    // Check if we're still on login page
    if (page.url().includes('/login')) {
      await page.waitForTimeout(2000); // Wait for error message
      const token = await page.evaluate(() => localStorage.getItem('access_token'));
      if (token) {
        // Token exists but navigation didn't happen - force navigation
        await page.goto('/');
      } else {
        const errorElement = page.locator('.error-message, .error-display');
        if ((await errorElement.count()) > 0) {
          const errorText = await errorElement.textContent();
          throw new Error(`Login failed: ${errorText}`);
        }
        throw new Error('Login failed: No token stored in localStorage');
      }
    }
  }

  // Wait for page to be ready (domcontentloaded, not networkidle)
  await page.waitForLoadState('domcontentloaded');

  // Wait for auth to be initialized - check that we're not on login page
  // and that localStorage has token (after 429 retry the app may take a moment to store)
  // Use explicit waitForFunction with smaller timeout increments
  let authInitialized = false;
  for (let attempt = 0; attempt < 60 && !authInitialized; attempt++) {
    authInitialized = await page
      .evaluate(() => {
        const token = localStorage.getItem('access_token');
        const user = localStorage.getItem('user');
        return !!(token && user);
      })
      .catch(() => false);
    if (!authInitialized) {
      await page.waitForTimeout(1000); // Wait 1s between checks
    }
  }
  if (!authInitialized) {
    throw new Error('Auth initialization timeout: token or user not found in localStorage');
  }

  // Wait for app shell to be visible (header/sidebar) - better than fixed timeout
  try {
    await expect(page.locator('.app-header, .app-sidebar')).toBeVisible({ timeout: 10000 });
  } catch {
    // If app shell not visible, check if we're still on login
    if (page.url().includes('/login')) {
      const errorElement = page.locator('.error-message, .error-display');
      const errorCount = await errorElement.count();
      if (errorCount > 0) {
        const errorText = await errorElement.textContent();
        throw new Error(`Login failed: ${errorText}`);
      }
      throw new Error('Login failed: Still on login page after auth initialization');
    }
  }
}
