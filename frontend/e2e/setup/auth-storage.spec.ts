/**
 * E2E Setup: Persist auth state for route specs (Phase 13).
 * Runs once before chromium/visible/chromium-routes; avoids per-test login and auth rate limits.
 * Real backend only; no mocks.
 * Uses UI login first (exercises proxy); falls back to API login + inject if UI fails.
 */

import { expect, test } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { getTestUser, loginViaApi } from '../fixtures/auth';

/** Wait for app shell after auth; allows up to 30s for capabilities and fetchUser. */
async function waitForAppShell(page: import('@playwright/test').Page): Promise<boolean> {
  return page
    .locator('.app-sidebar')
    .waitFor({ state: 'visible', timeout: 30000 })
    .then(() => true)
    .catch(() => false);
}

/** Inject API tokens into page and reload so app picks them up. */
async function injectAndReload(
  page: import('@playwright/test').Page,
  apiAuth: { access_token: string; refresh_token: string; user: object },
  base: string
): Promise<void> {
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ access_token, refresh_token, user: u }) => {
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    localStorage.setItem('user', JSON.stringify(u));
  }, apiAuth);
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  const shellVisible = await waitForAppShell(page);
  if (!shellVisible && page.url().includes('/login')) {
    throw new Error(
      'Auth storage: API login succeeded but app still on /login after reload. ' +
        'Check that authStore.initialize() reads from localStorage and VITE_PROXY_TARGET matches backend.'
    );
  }
}

const AUTH_DIR = path.join(process.cwd(), 'e2e', '.auth');
const STORAGE_STATE_PATH = path.join(AUTH_DIR, 'user.json');

test.describe('Auth storage setup', () => {
  test.setTimeout(300000); // 5 min: webServer startup + API login + inject + reload
  test('save authenticated session for route specs', async ({ page, baseURL }) => {
    const user = await getTestUser();
    const base = baseURL || 'http://localhost:5173';

    // Reset auth rate limits so login and fetchUser succeed (avoids 429 after prior runs)
    try {
      const { execSync } = await import('child_process');
      execSync('docker exec hub-test-api python hub/manage.py reset_e2e_auth_rate_limits', {
        stdio: 'pipe',
        encoding: 'utf8',
      });
    } catch {
      // Ignore if docker/command unavailable
    }

    // 1. Try UI login first (exercises proxy; API inject can fail if proxy misconfigured)
    const attemptLogin = async (): Promise<boolean> => {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
      await page.waitForSelector('input#password, input[type="password"]', { timeout: 10000 });
      const emailInput = page.locator('input#email').or(page.locator('input[type="email"]'));
      const passwordInput = page
        .locator('input#password')
        .or(page.locator('input[type="password"]'));
      await emailInput.fill(user.email);
      await passwordInput.fill(user.password);
      const submitButton = page
        .locator('button[type="submit"]')
        .or(page.locator('button.login-button'));
      await submitButton.waitFor({ state: 'visible', timeout: 10000 });
      const responsePromise = page.waitForResponse((r) => r.url().includes('/auth/login/'), {
        timeout: 60000,
      });
      await submitButton.click();
      let resp;
      try {
        resp = await responsePromise;
      } catch {
        return false;
      }
      if (resp.status() === 429) return false;
      if (resp.status() !== 200) return false;
      await page
        .waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 })
        .catch(() => {});
      const hasToken = await page
        .waitForFunction(
          () => !!(localStorage.getItem('access_token') && localStorage.getItem('user')),
          { timeout: 60000 }
        )
        .then(() => true)
        .catch(() => false);
      return hasToken;
    };

    let ok = await attemptLogin();
    if (!ok) {
      // 2. Fallback: API login and inject (when UI fails e.g. proxy/network)
      let apiAuth: Awaited<ReturnType<typeof loginViaApi>> | null = null;
      try {
        apiAuth = await loginViaApi(user.email, user.password);
      } catch {
        // API unavailable; will retry UI below
      }
      if (apiAuth) {
        await injectAndReload(page, apiAuth, base);
      } else {
        for (let retry = 0; retry < 3; retry++) {
          await page.waitForTimeout(65000);
          ok = await attemptLogin();
          if (ok) break;
        }
        if (!ok) {
          throw new Error(
            'Auth storage: UI and API login failed. Ensure backend is running and VITE_PROXY_TARGET points to it.'
          );
        }
      }
    }

    const hasToken = await page.evaluate(
      () => !!(localStorage.getItem('access_token') && localStorage.getItem('user'))
    );
    expect(hasToken).toBe(true);

    fs.mkdirSync(AUTH_DIR, { recursive: true });
    await page.context().storageState({ path: STORAGE_STATE_PATH });
    const currentUrl = page.url();
    expect(currentUrl).not.toContain('/login');
  });
});
