/**
 * Auth Test Fixtures
 * Helper functions for authentication in E2E tests
 */

import { Page, expect } from '@playwright/test';
import { E2E_APP_NAME } from './brand';
import { isBenignConsoleError } from './console-utils';
import {
  ensureAuditorUser,
  ensureComplianceOfficerUser,
  ensureConsumerTestUser,
  ensureDataMeshDomainOwnerUser,
  ensureExternalDeveloperUser,
  ensurePlatformAdminUser,
  ensureTenantAdminUser,
  ensureTestUser,
  type TestUser,
} from '../setup/create-test-user';

export type { TestUser };

// Node fetch needs absolute URL; VITE_API_BASE_URL can be relative (/api/v1)
// Prefer 8001 when E2E_WEB_PORT set (test stack uses 8001)
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http')
    ? process.env.VITE_API_BASE_URL
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

/** True when error is ECONNREFUSED (wrong port or backend not running). */
function isConnectionRefused(err: unknown): boolean {
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  const msg = String((err as Error)?.message ?? '');
  const causeMsg = cause && typeof cause === 'object' ? String((cause as Error)?.message ?? '') : '';
  const code = cause && typeof cause === 'object' ? (cause as { code?: string }).code : undefined;
  return code === 'ECONNREFUSED' || /ECONNREFUSED/i.test(msg) || /ECONNREFUSED/i.test(causeMsg);
}

/** True when error is a transient connection/network failure (try alternate port). */
function isConnectionError(err: unknown): boolean {
  const msg = String((err as Error)?.message ?? '');
  if (
    /ECONNREFUSED|ERR_CONNECTION_REFUSED|CONNECTION_REFUSED|ECONNRESET|socket hang up|other side closed|fetch failed/i.test(
      msg
    )
  )
    return true;
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'ECONNREFUSED' || c.code === 'ECONNRESET' || c.code === 'UND_ERR_SOCKET')
      return true;
    if (typeof c.message === 'string' && /other side closed|socket hang up/i.test(c.message))
      return true;
  }
  return false;
}

/** True when page/context/browser was closed (test timed out). */
function isPageClosedError(err: unknown): boolean {
  const msg = String(err);
  return (
    /Target page, context or browser has been closed|page has been closed|Protocol error.*Target closed|Execution context was destroyed/i.test(
      msg
    )
  );
}

/** Navigate with retry on connection errors (frontend server may be starting or under load). */
async function gotoWithRetry(
  page: Page,
  url: string,
  options: { waitUntil?: 'domcontentloaded' | 'load' } = {},
  maxRetries = 4
): Promise<void> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      await page.goto(url, { waitUntil: options.waitUntil ?? 'domcontentloaded' });
      return;
    } catch (err) {
      if (isPageClosedError(err)) {
        throw new Error(
          `page.goto: Page/context/browser was closed (test likely timed out). Increase test.setTimeout.`
        );
      }
      if (isConnectionError(err) && attempt < maxRetries - 1) {
        const delay = 2000 * (attempt + 1);
        console.log(
          `page.goto(${url}) failed (connection error), retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})...`
        );
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      if (isConnectionError(err)) {
        throw new Error(
          `page.goto: Frontend server unreachable (connection refused). ` +
            `Ensure the E2E web server is running (Playwright webServer or 'npm run dev'). Original: ${(err as Error).message}`
        );
      }
      throw err;
    }
  }
}

/** Alternate API port for localhost (8000 <-> 8001) when primary refuses connection. */
function getAlternateApiBase(currentBase: string): string | null {
  try {
    const url = new URL(currentBase);
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
      const port = parseInt(url.port || '80', 10);
      const altPort = port === 8001 ? 8000 : port === 8000 ? 8001 : null;
      if (altPort) {
        url.port = String(altPort);
        return url.toString();
      }
    }
  } catch {
    // ignore
  }
  return null;
}

interface ApiAuth {
  access_token: string;
  refresh_token: string;
  user: { id: string; email: string; name: string; roles: string[]; [k: string]: unknown };
}

/** API login + inject tokens into page. Used for 429/500 fallback; use UI login for normal flow. */
async function loginViaApiAndInject(page: Page, user: TestUser): Promise<void> {
  const apiAuth = await loginViaApi(user.email, user.password);
  // Use relative URL so Playwright resolves via baseURL (handles E2E_WEB_PORT, etc.)
  await gotoWithRetry(page, '/');
  await page.evaluate(
    ({ access_token, refresh_token, user: u }) => {
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      localStorage.setItem('user', JSON.stringify(u));
    },
    apiAuth
  );
  await gotoWithRetry(page, '/', { waitUntil: 'load' });
  // Wait for auth init + capabilities; app shell appears after fetchUser completes.
  // Under parallel E2E load, capabilities API can return 500 and delay; use 90s.
  const shellTimeout = process.env.E2E_WEB_PORT ? 90000 : 60000;
  const shellLocator = page.locator('.app-header, .app-sidebar').first();
  for (let attempt = 0; attempt <= 2; attempt++) {
    try {
      await shellLocator.waitFor({ state: 'visible', timeout: shellTimeout });
      break;
    } catch (err) {
      if (isPageClosedError(err)) {
        throw new Error(
          'loginViaApiAndInject: Page/context/browser was closed. Increase test.setTimeout.'
        );
      }
      if (attempt < 2) {
        try {
          await page.reload({ waitUntil: 'load' });
        } catch (reloadErr) {
          if (isPageClosedError(reloadErr)) {
            throw new Error(
              'loginViaApiAndInject: Page closed during reload. Increase test.setTimeout.'
            );
          }
          throw reloadErr;
        }
        await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
      } else {
        throw new Error(
          `loginViaApiAndInject: App shell (.app-header, .app-sidebar) not visible within ${shellTimeout}ms after ${attempt + 1} attempts. ` +
            `Capabilities API may be failing (500). URL: ${page.url()}. Original: ${(err as Error).message}`
        );
      }
    }
  }
}

/** Decode JWT payload (base64url) to get user claims; avoids /auth/me/ when rate-limited. */
function userFromAccessToken(accessToken: string): ApiAuth['user'] {
  const parts = accessToken.split('.');
  if (parts.length !== 3) throw new Error('Invalid JWT format');
  const payload = JSON.parse(
    Buffer.from(parts[1].replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString()
  ) as { sub?: string; email?: string; name?: string; roles?: string[]; tenant_id?: string };
  return {
    id: payload.sub ?? '',
    email: payload.email ?? '',
    name: payload.name ?? '',
    roles: Array.isArray(payload.roles) ? payload.roles : [],
    tenant_id: payload.tenant_id,
  };
}

const LOGIN_RETRY_DELAYS_MS = [2000, 4000, 6000, 8000, 10000];

function isRetryable500(err: unknown): boolean {
  const msg = String((err as Error)?.message ?? '');
  return (
    /API login failed: 500/.test(msg) &&
    /translate host name|name resolution|getaddrinfo|ENOTFOUND|could not translate|postgres/i.test(msg)
  );
}

/** Login via backend API from Node; returns tokens and user for storage injection.
 * Retries on transient connection errors and 500 host-resolution. Tries alternate port (8000 <-> 8001) on ECONNREFUSED.
 * When both ports fail (API restart during E2E), retries once after 10s delay. */
export async function loginViaApi(
  email: string,
  password: string,
  options?: { connectionRetryCount?: number }
): Promise<ApiAuth> {
  const connectionRetryCount = options?.connectionRetryCount ?? 0;
  const basesToTry = [API_BASE];
  const alt = getAlternateApiBase(API_BASE);
  if (alt) basesToTry.push(alt);

  let lastErr: unknown;
  for (const base of basesToTry) {
    for (let r = 0; r < LOGIN_RETRY_DELAYS_MS.length + 1; r++) {
      try {
        const loginRes = await fetch(`${base}/auth/login/`, {
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

        const meRes = await fetch(`${base}/auth/me/`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${loginData.access_token}` },
        });
        if (meRes.ok) {
          const user = (await meRes.json()) as ApiAuth['user'];
          return {
            access_token: loginData.access_token,
            refresh_token: loginData.refresh_token,
            user,
          };
        }
        if (meRes.status === 429 || meRes.status >= 500) {
          // Rate-limited or transient server error: use token payload to avoid blocking tests
          return {
            access_token: loginData.access_token,
            refresh_token: loginData.refresh_token,
            user: userFromAccessToken(loginData.access_token),
          };
        }
        throw new Error(`API /auth/me/ failed: ${meRes.status}`);
      } catch (err) {
        lastErr = err;
        const retryable =
          (r < LOGIN_RETRY_DELAYS_MS.length && (isConnectionRefused(err) || isConnectionError(err))) ||
          (r < 4 && isRetryable500(err));
        if (retryable) {
          const delay = LOGIN_RETRY_DELAYS_MS[Math.min(r, LOGIN_RETRY_DELAYS_MS.length - 1)] ?? 10000;
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
        if (isConnectionRefused(err) || isConnectionError(err)) {
          break; // Try alternate port
        }
        throw err;
      }
    }
  }
  // When both bases failed with connection error, API may be restarting during E2E; retry once after delay
  if (
    lastErr &&
    connectionRetryCount < 1 &&
    (isConnectionRefused(lastErr) || isConnectionError(lastErr))
  ) {
    await new Promise((resolve) => setTimeout(resolve, 10000));
    return loginViaApi(email, password, { connectionRetryCount: connectionRetryCount + 1 });
  }
  throw lastErr ?? new Error('loginViaApi: unexpected');
}

/**
 * Clear auth state so the page behaves as unauthenticated.
 * Use before auth journey tests that need to see login/register/public/password-reset pages
 * when running with chromium-routes (stored session).
 * Defensive: handles page-closed (test timeout) and navigation failures.
 */
export async function clearAuthStorage(page: Page): Promise<void> {
  try {
    try {
      // Use 45s timeout: the visible/slowMo project (400ms per action) can cause the previous
      // page to be slow, making domcontentloaded take longer than the old 15s budget.
      await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 45000 });
    } catch (navErr) {
      if (isPageClosedError(navErr)) {
        return; // Page/context closed (test timeout); absorb to avoid cascading
      }
      const navMsg = String(navErr);
      if (
        /interrupted by another navigation/i.test(navMsg) ||
        /ERR_ABORTED/i.test(navMsg) ||
        /net::ERR_/i.test(navMsg)
      ) {
        // Navigation was interrupted because the app simultaneously redirected to /login.
        // The page should already be on /login — wait for it to settle, then continue.
        await page.waitForLoadState('domcontentloaded').catch(() => {});
      } else {
        throw navErr;
      }
    }
    await page.waitForLoadState('domcontentloaded');
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('active_tenant_id');
      sessionStorage.clear();
    }).catch((e) => {
      const msg = String(e);
      const pageClosed =
        /Execution context was destroyed|Target closed|page has been closed|context or browser has been closed|Protocol error.*closed/i.test(
          msg
        );
      if (!pageClosed) throw e;
      // Page/context closed during clear (e.g. test timeout); absorb - avoid cascading error
    });
    // Intentional: clearCookies is best-effort; may fail if context closed during teardown
    await page.context().clearCookies().catch(() => {});
    // Reload so app re-initializes with empty storage (auth store + apiClient).
    // Without this, apiClient keeps in-memory tokens and 401 on confirm can trigger redirect.
    await page.reload({ waitUntil: 'load' });
  } catch (err) {
    const msg = String(err);
    const pageClosed =
      /Target page, context or browser has been closed|page has been closed|Protocol error.*closed|closed during clear|Execution context was destroyed/i.test(
        msg
      );
    if (pageClosed) {
      // Page/context closed (test timed out); absorb to avoid cascading error
      return;
    }
    throw err;
  }
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
 * Get tenant admin test user (TA). Requires ensure_e2e_user_roles run before E2E.
 */
export async function getTenantAdminUser(): Promise<TestUser> {
  return await ensureTenantAdminUser();
}

/**
 * Get tenant admin or fall back to test user when tenant admin is unavailable (e.g. transient setup race).
 * Use for ODPS/DE-014 when tenant admin may not be ready; test user may have access in default tenant.
 */
export async function getTenantAdminUserOrTestUser(): Promise<TestUser> {
  try {
    return await ensureTenantAdminUser();
  } catch {
    return await ensureTestUser();
  }
}

/**
 * Get auditor test user (AUD). Requires ensure_e2e_user_roles run before E2E.
 */
export async function getAuditorUser(): Promise<TestUser> {
  return await ensureAuditorUser();
}

/**
 * Get platform admin test user (PA). Requires ensure_e2e_user_roles run before E2E.
 */
export async function getPlatformAdminUser(): Promise<TestUser> {
  return await ensurePlatformAdminUser();
}

/**
 * Get compliance officer test user (CPO). Requires ensure_e2e_user_roles run before E2E.
 */
export async function getComplianceOfficerUser(): Promise<TestUser> {
  return await ensureComplianceOfficerUser();
}

/**
 * Get external developer test user (DEV). Requires ensure_e2e_user_roles run before E2E.
 */
export async function getExternalDeveloperUser(): Promise<TestUser> {
  return await ensureExternalDeveloperUser();
}

/**
 * Get data mesh domain owner test user (DMO). Requires ensure_e2e_user_roles run before E2E.
 */
export async function getDataMeshDomainOwnerUser(): Promise<TestUser> {
  return await ensureDataMeshDomainOwnerUser();
}

/**
 * Clear auth and login as a specific persona. Use when the default storageState (e2e_test)
 * would cause 403 on role-gated routes. Required for AUD, TA, PA, CPO, DEV, DMO specs.
 */
export async function loginAsPersona(page: Page, getUser: () => Promise<TestUser>): Promise<void> {
  await clearAuthStorage(page);
  const user = await getUser();
  await loginUser(page, user);
}

export interface LoginUserOptions {
  /** When true, use UI login. Default: true; API inject used only for 429 fallback. */
  useUiLogin?: boolean;
  /** When true, skip early-exit and always do full UI login. Use when protected routes redirect to login. */
  forceFreshLogin?: boolean;
}

/**
 * Login user via UI (default). When using storageState, skips if already authenticated.
 * On 429 after retries, falls back to API login and injects tokens.
 */
export async function loginUser(
  page: Page,
  user: TestUser,
  options: LoginUserOptions = {}
): Promise<void> {
  const { useUiLogin = true, forceFreshLogin = false } = options;
  // Capture console errors (filter expected 404/not-found from failure tests)
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (!isBenignConsoleError(text)) {
        consoleErrors.push(text);
        console.log(`Browser console error: ${text}`);
      }
    }
  });

  // Navigate to login page (retry on connection errors when frontend is starting/under load)
  await gotoWithRetry(page, '/login');

  // Early exit: already authenticated as the SAME user (storageState from setup-auth)
  // Token may be expired; if we get redirected to /login, fall through to full login
  const storedAuth = await page
    .evaluate(() => {
      const token = localStorage.getItem('access_token');
      const u = localStorage.getItem('user');
      if (!token || !u) return null;
      try {
        const parsed = JSON.parse(u) as { email?: string };
        return parsed?.email ?? null;
      } catch {
        return null;
      }
    })
    .catch((e: unknown) => {
      const msg = String(e);
      if (/Target page, context or browser has been closed|page has been closed/i.test(msg)) {
        throw new Error(
          'loginUser: Page/context/browser was closed (test likely timed out). Increase test.setTimeout.'
        );
      }
      // Intentional: when evaluate fails (e.g. context destroyed, malformed user JSON), assume no stored auth
      return null;
    });
  const sameUser = storedAuth && storedAuth === user.email;
  const alreadyLoggedIn = !!storedAuth;
  if (!forceFreshLogin && sameUser && (alreadyLoggedIn || !page.url().includes('/login'))) {
    await gotoWithRetry(page, '/');
    // Give app shell 30s; capabilities can be slow under E2E load (multiple workers)
    try {
      await page.locator('.app-sidebar').waitFor({ state: 'visible', timeout: 30000 });
      // Verify auth is stable: wait for fetchUser to complete; if token expired we get redirected
      await page.waitForTimeout(2000);
      if (!page.url().includes('/login')) {
        return;
      }
      // Redirected to login – token expired
    } catch (err) {
      if (isPageClosedError(err)) {
        throw new Error(
          'loginUser: Page/context/browser was closed (test likely timed out). Increase test.setTimeout.'
        );
      }
      // App shell not visible: fall through to fresh login (avoids flake when page is loading or in bad state)
    }
    await clearAuthStorage(page);
    await gotoWithRetry(page, '/login');
    // Fall through to login form handling below
  }

  // No valid stored auth – need full login via UI
  if (!storedAuth || !sameUser) {
    await clearAuthStorage(page);
    await gotoWithRetry(page, '/login');
  }

  // Wait for React to hydrate - first wait for the h1 (like login-app-shell test)
  await page.waitForLoadState('domcontentloaded');
  let h1Found = false;
  for (let attempt = 0; attempt < 3 && !h1Found; attempt++) {
    try {
      await page.waitForSelector('h1', { timeout: attempt === 0 ? 10000 : 8000 });
      await expect(page.locator('h1')).toContainText(E2E_APP_NAME, { timeout: 5000 });
      h1Found = true;
    } catch {
      if (attempt < 2) {
        await page.waitForTimeout(3000);
      } else {
        const bodyText = await page.textContent('body');
        console.log('Page body (first 500 chars):', bodyText?.substring(0, 500));
        throw new Error(`Login page h1 not found. Page content: ${bodyText?.substring(0, 200)}`);
      }
    }
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

  // Submit form and wait for login API response (60s for Docker API under parallel E2E load)
  // On 429 (rate limit), retry with backoff so E2E suite can complete without flake
  // On 500 (server error), retry - OpenAPI/capabilities may cause transient 500s under parallel load
  // On timeout (API slow under load), fall back to API login
  const loginResponseTimeout = process.env.E2E_WEB_PORT ? 60000 : 30000;
  const attemptLogin = async (): Promise<{ status: number; body: string } | null> => {
    const responsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes('/auth/login/') &&
        (resp.status() === 200 || resp.status() === 429 || resp.status() === 500),
      { timeout: loginResponseTimeout }
    );
    await submitButton.click();
    try {
      const resp = await responsePromise;
      // Intentional fallback: response body may be non-text when parsing fails
      const body = await resp.text().catch(() => '');
      return { status: resp.status(), body };
    } catch (err) {
      if (String(err).includes('Timeout') || String(err).includes('timeout')) {
        return null;
      }
      throw err;
    }
  };

  let loginResponse = await attemptLogin();
  if (loginResponse === null) {
    await loginViaApiAndInject(page, user);
    return;
  }
  // On 500: retry up to 2 times (transient server errors from OpenAPI/capabilities under load)
  for (let retries = 0; retries < 2 && loginResponse.status === 500; retries++) {
    await page.waitForTimeout(3000);
    await gotoWithRetry(page, '/login');
    await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
    await emailInput.fill(user.email);
    await passwordInput.fill(user.password);
    const retryResp = await attemptLogin();
    if (retryResp === null) {
      await loginViaApiAndInject(page, user);
      return;
    }
    loginResponse = retryResp;
  }
  // On 429: retry UI login up to 2 times, then fall back to API login to avoid rate-limit exhaustion
  for (let retries = 0; retries < 2 && loginResponse.status === 429; retries++) {
    await page.waitForTimeout(15000);
    await gotoWithRetry(page, '/login');
    await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
    await emailInput.fill(user.email);
    await passwordInput.fill(user.password);
    const retryResp = await attemptLogin();
    if (retryResp === null) {
      await loginViaApiAndInject(page, user);
      return;
    }
    loginResponse = retryResp;
  }
  if (loginResponse.status === 429) {
    await loginViaApiAndInject(page, user);
    return;
  }
  if (loginResponse.status === 500) {
    // Fallback to API login when UI login returns 500 (e.g. OpenAPI/capabilities under load)
    await loginViaApiAndInject(page, user);
    return;
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
      try {
        await page.waitForTimeout(2000); // Wait for error message
      } catch (waitErr) {
        if (isPageClosedError(waitErr)) {
          throw new Error(
            'loginUser: Page/context/browser was closed during auth init. Increase test.setTimeout.'
          );
        }
        throw waitErr;
      }
      const token = await page.evaluate(() => localStorage.getItem('access_token'));
      if (token) {
        // Token exists but navigation didn't happen - force navigation
        await gotoWithRetry(page, '/');
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
  for (let attempt = 0; attempt < 30 && !authInitialized; attempt++) {
    try {
      authInitialized = await page.evaluate(() => {
        const token = localStorage.getItem('access_token');
        const user = localStorage.getItem('user');
        return !!(token && user);
      });
    } catch (err) {
      if (isPageClosedError(err)) {
        throw new Error(
          'loginUser: Page/context/browser was closed during auth init. Increase test.setTimeout.'
        );
      }
      // Other errors (e.g. context destroyed): treat as not initialized
      authInitialized = false;
    }
    if (!authInitialized) {
      try {
        await page.waitForTimeout(1000); // Wait 1s between checks
      } catch (err) {
        if (isPageClosedError(err)) {
          throw new Error(
            'loginUser: Page/context/browser was closed during auth init. Increase test.setTimeout.'
          );
        }
        throw err;
      }
    }
  }
  if (!authInitialized) {
    // UI login returned 200 but app didn't persist token/user (race under parallel E2E load).
    // Fall back to API login + inject so tests can proceed.
    await loginViaApiAndInject(page, user);
    return;
  }

  // Wait for app shell to be visible (header/sidebar) - allow 30s when capabilities are slow
  // Use .first() to avoid strict mode violation when both header and sidebar match
  try {
    await expect(page.locator('.app-header, .app-sidebar').first()).toBeVisible({ timeout: 30000 });
  } catch (err) {
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
    // Not on login but shell not visible - propagate the failure
    throw err;
  }

  // Verify auth is stable: wait for fetchUser; if token invalid we get redirected to login
  try {
    await page.waitForTimeout(2000);
  } catch (waitErr) {
    if (isPageClosedError(waitErr)) {
      throw new Error(
        'loginUser: Page/context/browser was closed during auth init. Increase test.setTimeout.'
      );
    }
    throw waitErr;
  }
  if (page.url().includes('/login')) {
    throw new Error(
      'Login failed: Redirected to login after app shell appeared; token may be invalid.'
    );
  }
}
