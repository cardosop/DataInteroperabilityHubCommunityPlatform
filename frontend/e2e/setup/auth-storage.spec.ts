/**
 * E2E Setup: Persist auth state for route specs (Phase 13).
 * Runs once before chromium-routes; avoids per-test login and auth rate limits.
 * Real backend only; no mocks.
 * If UI login times out (e.g. proxy/network), falls back to API login and injects tokens into page.
 */

import { expect, test } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { getTestUser } from '../fixtures/auth';

const AUTH_DIR = path.join(process.cwd(), 'e2e', '.auth');
const STORAGE_STATE_PATH = path.join(AUTH_DIR, 'user.json');
const API_BASE = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface ApiAuth {
  access_token: string;
  refresh_token: string;
  user: { id: string; email: string; name: string; roles: string[]; [k: string]: unknown };
}

/** Login via backend API from Node; returns tokens and user for storage injection. */
async function loginViaApi(email: string, password: string): Promise<ApiAuth> {
  const loginRes = await fetch(`${API_BASE}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!loginRes.ok) {
    const text = await loginRes.text();
    throw new Error(`API login failed: ${loginRes.status} ${text}`);
  }
  const loginData = (await loginRes.json()) as {
    access_token: string;
    refresh_token: string;
  };
  const meRes = await fetch(`${API_BASE}/auth/me/`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${loginData.access_token}` },
  });
  if (!meRes.ok) {
    throw new Error(`API /auth/me/ failed: ${meRes.status}`);
  }
  const user = (await meRes.json()) as ApiAuth['user'];
  return {
    access_token: loginData.access_token,
    refresh_token: loginData.refresh_token,
    user,
  };
}

test.describe('Auth storage setup', () => {
  test.setTimeout(300000);
  test('save authenticated session for route specs', async ({ page, baseURL }) => {
    const user = await getTestUser();
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
      // Accept any response from login URL so we don't timeout on 401/500; handle below
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
    for (let retry = 0; !ok && retry < 3; retry++) {
      await page.waitForTimeout(65000);
      ok = await attemptLogin();
    }

    if (!ok) {
      // Fallback: login via API and inject into page so route specs get valid session
      const apiAuth = await loginViaApi(user.email, user.password);
      await page.goto(baseURL || 'http://localhost:5173/', { waitUntil: 'domcontentloaded' });
      await page.evaluate(({ access_token, refresh_token, user: u }) => {
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        localStorage.setItem('user', JSON.stringify(u));
      }, apiAuth);
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
