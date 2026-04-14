/**
 * Auth Test Fixtures
 * Helper functions for authentication in E2E tests
 */

import { Page, expect } from '@playwright/test';
import { E2E_APP_NAME } from './brand';
import {
  ensureAuditorUser,
  ensureComplianceOfficerUser,
  ensureConsumerTestUser,
  ensureDataMeshDomainOwnerUser,
  ensureExternalDeveloperUser,
  ensurePlatformAdminUser,
  ensureTenantAdminUser,
  ensureProfileIsolationUser,
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
    /Target page, context or browser has been closed|page has been closed|Protocol error.*Target closed|Execution context was destroyed|Not attached to an active page/i.test(
      msg
    )
  );
}

/** True when error is a navigation timeout (page.goto exceeded its per-attempt timeout). */
function isNavigationTimeout(err: unknown): boolean {
  const msg = String((err as Error)?.message ?? '');
  // Playwright throws "Timeout NNNNms exceeded" or "Test timeout of NNNNms exceeded" for timeouts.
  // Only retry when the error is NOT from the overall test timeout (which includes "Test timeout").
  if (/Test timeout/i.test(msg)) return false;
  return /timeout.*exceeded|Timeout/i.test(msg);
}

/** Navigate with retry on connection errors and navigation timeouts. */
export async function gotoWithRetry(
  page: Page,
  url: string,
  options: { waitUntil?: 'commit' | 'domcontentloaded' | 'load' } = {},
  maxRetries = 4
): Promise<void> {
  // Use a per-attempt timeout (30s) so a single hung navigation doesn't consume the entire test budget
  const perAttemptTimeout = 30_000;
  // Default 'commit': completes when the navigation response is committed. Under parallel E2E
  // against Vite dev, waiting for domcontentloaded can stall while the transform graph is busy;
  // callers already use waitForLoadState / waitForAppMainReady / locators for real readiness.
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      await page.goto(url, {
        waitUntil: options.waitUntil ?? 'commit',
        timeout: perAttemptTimeout,
      });
      return;
    } catch (err) {
      if (isPageClosedError(err)) {
        throw new Error(
          `page.goto: Page/context/browser was closed (test likely timed out). Increase test.setTimeout.`
        );
      }
      const isRetryable = isConnectionError(err) || isNavigationTimeout(err);
      if (isRetryable && attempt < maxRetries - 1) {
        const delay = 2000 * (attempt + 1);
        const reason = isConnectionError(err) ? 'connection error' : 'navigation timeout';
        console.log(
          `page.goto(${url}) failed (${reason}), retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})...`
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
  /** Refresh token extracted from the Set-Cookie header (11.1); may be empty string. */
  refresh_token: string;
  user: { id: string; email: string; name: string; roles: string[]; [k: string]: unknown };
}

/**
 * Write API login result into the browser: localStorage (access + refresh + user) and refresh
 * cookie. Keeps session facets aligned — avoids E2E flakes where a fresh access_token was applied
 * but an older refresh_token (storageState) remained, causing broken refresh / redirect-to-login
 * after navigation.
 */
async function syncPageWithApiAuth(page: Page, apiAuth: ApiAuth): Promise<void> {
  await page.evaluate(
    ({ access_token, refresh_token, user: u }) => {
      localStorage.setItem('access_token', access_token);
      if (refresh_token) {
        localStorage.setItem('refresh_token', refresh_token);
      }
      localStorage.setItem('user', JSON.stringify(u));
    },
    {
      access_token: apiAuth.access_token,
      refresh_token: apiAuth.refresh_token,
      user: apiAuth.user,
    }
  );
  if (apiAuth.refresh_token) {
    try {
      const pageUrl = page.url();
      const cookieDomain = pageUrl.startsWith('http')
        ? new URL(pageUrl).hostname
        : 'localhost';
      await page.context().addCookies([
        {
          name: 'refresh_token',
          value: apiAuth.refresh_token,
          domain: cookieDomain,
          path: '/',
          httpOnly: true,
          secure: false,
          sameSite: 'Strict',
        },
      ]);
    } catch {
      // Cookie injection is best-effort; localStorage refresh still enables authService.refresh
    }
  }
}

/**
 * API login + inject tokens into page. Used for 429/500 fallback; use UI login for normal flow.
 *
 * 11.1: access_token is stored in localStorage (read by authService.initializeAuth() for E2E
 * compat); refresh_token is injected as an httpOnly cookie via page.context().addCookies().
 * refresh_token is no longer written to localStorage.
 */
async function loginViaApiAndInject(page: Page, user: TestUser): Promise<void> {
  const apiAuth = await loginViaApi(user.email, user.password);
  // Use relative URL so Playwright resolves via baseURL (handles E2E_WEB_PORT, etc.)
  await gotoWithRetry(page, '/');
  await syncPageWithApiAuth(page, apiAuth);
  await gotoWithRetry(page, '/', { waitUntil: 'domcontentloaded' });
  // Fast health probe: if the backend is completely down, fail fast instead of waiting 90s×2.
  // This saves 3+ minutes per test when the capabilities API is returning 500.
  try {
    const healthRes = await page.request.get('/api/v1/health/live/', { timeout: 10000 }).catch(() => null);
    if (healthRes && healthRes.status() >= 500) {
      throw new Error(
        `loginViaApiAndInject: Backend health check returned ${healthRes.status()}. ` +
          'Capabilities API is likely failing — app shell will not render.'
      );
    }
  } catch (healthErr) {
    if ((healthErr as Error).message?.includes('loginViaApiAndInject')) throw healthErr;
    // Health endpoint not available (404, network error) — continue with shell wait
  }
  // Wait for auth init + capabilities; app shell appears after fetchUser completes.
  // With statement_timeout=120s in test DB, capabilities should load in <15s normally.
  // 45s shell wait allows for slow capabilities + token refresh under parallel load.
  const shellTimeout = 45000;
  const shellLocator = page.locator('.app-header, .app-sidebar').first();
  // 2 attempts: worst case 45s + reload + 45s = ~95s (fits within 120s test timeout).
  for (let attempt = 0; attempt <= 1; attempt++) {
    try {
      await shellLocator.waitFor({ state: 'visible', timeout: shellTimeout });
      break;
    } catch (err) {
      if (isPageClosedError(err)) {
        throw new Error(
          'loginViaApiAndInject: Page/context/browser was closed. Increase test.setTimeout.'
        );
      }
      if (attempt < 1) {
        try {
          await page.reload({ waitUntil: 'domcontentloaded' });
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
  if (!/API login failed: 500/.test(msg)) return false;
  // Host resolution (postgres container DNS), statement timeout (DB overloaded under parallel
  // E2E load), deadlock/lock timeout, too many connections — all transient under E2E.
  return /translate host name|name resolution|getaddrinfo|ENOTFOUND|could not translate|postgres|statement timeout|canceling statement|deadlock|lock timeout|too many connections|too many clients/i.test(msg);
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
        if (loginRes.status === 429) {
          // Rate-limited: backoff and retry instead of failing immediately.
          // Parallel E2E workers saturate the rate limiter — this is expected, not a bug.
          const retryAfter = parseInt(loginRes.headers.get('retry-after') ?? '', 10);
          const backoffMs = (retryAfter > 0 ? retryAfter * 1000 : LOGIN_RETRY_DELAYS_MS[Math.min(r, LOGIN_RETRY_DELAYS_MS.length - 1)] ?? 10000);
          await new Promise((resolve) => setTimeout(resolve, backoffMs));
          continue;
        }
        if (loginRes.status >= 500) {
          // 500 may be a transient deadlock under parallel E2E load — retry with backoff.
          const text = await loginRes.text();
          const isTransient = /deadlock|lock timeout|connection reset|too many connections/i.test(text);
          if (isTransient && r < LOGIN_RETRY_DELAYS_MS.length) {
            const backoffMs = LOGIN_RETRY_DELAYS_MS[r] ?? 10000;
            await new Promise((resolve) => setTimeout(resolve, backoffMs));
            continue;
          }
          throw new Error(`API login failed: ${loginRes.status} ${text}`);
        }
        if (!loginRes.ok) {
          const text = await loginRes.text();
          throw new Error(`API login failed: ${loginRes.status} ${text}`);
        }
        const loginData = (await loginRes.json()) as {
          access_token: string;
          refresh_token?: string; // absent after 11.1 — delivered as httpOnly cookie
        };

        // Extract refresh token from Set-Cookie header (11.1).
        // Node fetch returns the raw header string; parse the value before the first ';'.
        const setCookieHeader = loginRes.headers.get('set-cookie') ?? '';
        const refreshCookieMatch = setCookieHeader.match(/(?:^|,\s*)refresh_token=([^;,]+)/i);
        const refresh_token = refreshCookieMatch?.[1] ?? loginData.refresh_token ?? '';

        const meRes = await fetch(`${base}/auth/me/`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${loginData.access_token}` },
        });
        if (meRes.ok) {
          const user = (await meRes.json()) as ApiAuth['user'];
          return {
            access_token: loginData.access_token,
            refresh_token,
            user,
          };
        }
        if (meRes.status === 429 || meRes.status >= 500) {
          // Rate-limited or transient server error: use token payload to avoid blocking tests
          return {
            access_token: loginData.access_token,
            refresh_token,
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
      // Navigate to /login to get a page context for localStorage clearing.
      // Use 'commit' instead of 'domcontentloaded' — we only need the document to exist,
      // not for all scripts to load. This avoids hanging when Vite is slow or backend proxy stalls.
      await page.goto('/login', { waitUntil: 'commit', timeout: 30000 });
    } catch (navErr) {
      if (isPageClosedError(navErr)) {
        return; // Page/context closed (test timeout); absorb to avoid cascading
      }
      const navMsg = String(navErr);
      if (isNavigationTimeout(navErr)) {
        // Navigation timeout is non-fatal for clearAuthStorage: the purpose is
        // to get a page context for localStorage.clear(). If the page is already
        // on any route (from a previous test), evaluate() will work regardless.
        // Throwing here causes cascading failures in loginAsPersona on staging
        // where network latency makes 'commit' slow.
      } else if (
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
    // No additional waitForLoadState needed — page.goto with 'commit' already ensures
    // the document exists, which is all we need for page.evaluate(localStorage) below.
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('active_tenant_id');
      sessionStorage.clear();
    }).catch((e) => {
      const msg = String(e);
      const pageClosed =
        /Execution context was destroyed|Target closed|page has been closed|context or browser has been closed|Protocol error.*closed|Not attached to an active page/i.test(
          msg
        );
      if (!pageClosed) throw e;
      // Page/context closed during clear (e.g. test timeout); absorb - avoid cascading error
    });
    // Intentional: clearCookies is best-effort; may fail if context closed during teardown
    await page.context().clearCookies().catch(() => {});
    // Reload so app re-initializes with empty storage (auth store + apiClient).
    // Without this, apiClient keeps in-memory tokens and 401 on confirm can trigger redirect.
    // Use 'domcontentloaded' (not 'load') — the 'load' event waits for ALL sub-resources
    // (API calls, fonts, images). When auth init fires long-running /capabilities/ or
    // /auth/me/ requests on reload, 'load' never fires and the test timeout is consumed.
    // 'domcontentloaded' is sufficient: the DOM is ready and localStorage is cleared.
    // Best-effort: if reload times out (Vite dev server overloaded under parallel E2E load),
    // localStorage is already cleared — the next page.goto will re-initialize cleanly.
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch((reloadErr) => {
      const reloadMsg = String(reloadErr);
      const isTimeout = /[Tt]imeout/.test(reloadMsg);
      const isPageClosed =
        /Target.*closed|page has been closed|context.*closed|Execution context was destroyed|Not attached to an active page/i.test(reloadMsg);
      if (!isTimeout && !isPageClosed) throw reloadErr;
      // Timeout or page-closed during reload — localStorage is already cleared, safe to continue
    });
  } catch (err) {
    const msg = String(err);
    const pageClosed =
      /Target page, context or browser has been closed|page has been closed|Protocol error.*closed|closed during clear|Execution context was destroyed|Not attached to an active page/i.test(
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
 * User reserved for profile/display_name mutation E2E — one stable account per Playwright worker.
 */
export async function getProfileIsolationTestUser(workerIndex: number): Promise<TestUser> {
  return await ensureProfileIsolationUser(workerIndex);
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
  // Resolve user credentials (API call, may trigger subscription ensure)
  // concurrently with clearing auth — getUser() does Node.js HTTP calls
  // (no page interaction) so it can run while the page navigates.
  const [user] = await Promise.all([
    getUser(),
    clearAuthStorage(page),
  ]);
  // forceFreshLogin: true skips the fast-path (navigate to '/' and check
  // localStorage for stored user) which always fails after clearAuthStorage
  // and wastes 30s on a navigation timeout.  forceFreshLogin calls
  // clearAuthStorage again but it's fast when page is already on /login.
  await loginUser(page, user, { forceFreshLogin: true });
}

export interface LoginUserOptions {
  /** When true, use UI login. Default: true; API inject used only for 429 fallback. */
  useUiLogin?: boolean;
  /** When true, skip early-exit and always do full UI login. Use when protected routes redirect to login. */
  forceFreshLogin?: boolean;
  /**
   * When true, throw instead of falling back to loginViaApiAndInject.
   * Use in token-storage security tests where the fallback path would
   * write access_token to localStorage and invalidate the assertion.
   */
  failOnFallback?: boolean;
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
  const { forceFreshLogin = false, failOnFallback = false } = options;

  /**
   * Internal helper: either throws (when failOnFallback=true) or falls back to
   * API token injection. Security tests must pass failOnFallback=true so a
   * rate-limited or slow UI login doesn't silently corrupt auth storage state.
   */
  async function fallbackOrThrow(reason: string): Promise<void> {
    if (failOnFallback) {
      throw new Error(
        `[loginUser] UI login failed and failOnFallback=true — cannot fall back to ` +
        `API injection for this test (doing so would write access_token to localStorage ` +
        `and invalidate the auth-security assertion). Reason: ${reason}. ` +
        `Check backend rate limits or server health.`
      );
    }
    await loginViaApiAndInject(page, user);
  }
  // Performance optimization: when storageState has user profile for this user,
  // inject a fresh access_token via API login and navigate to '/'. This avoids
  // both the slow UI login form AND the proactive refresh race condition:
  // Phase 11.1 token rotation with replay detection means a shared refresh_token
  // from storageState can only be used once — the second parallel worker would
  // trigger replay detection and revoke the entire token family.
  // By doing a Node.js API login (which gets its own tokens), each test gets
  // independent auth credentials that don't interfere with other workers.
  if (!forceFreshLogin) {
    await gotoWithRetry(page, '/');
    const storedAuth = await page
      .evaluate(() => {
        const u = localStorage.getItem('user');
        if (!u) return null;
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
        return null;
      });
    const sameUser = storedAuth && storedAuth === user.email;
    if (sameUser) {
      // storageState has user profile — inject fresh tokens via API login (access + refresh + user)
      // and align the refresh cookie. Partial updates (access only) left stale refresh data and
      // caused redirect-to-login during client-side navigation under load.
      try {
        const apiAuth = await loginViaApi(user.email, user.password);
        await syncPageWithApiAuth(page, apiAuth);
        // Reload so authStore.initialize() picks up storage + cookie consistently
        await page.reload({ waitUntil: 'domcontentloaded' });
        await page.locator('.app-sidebar').waitFor({ state: 'visible', timeout: 30000 });
        if (!page.url().includes('/login')) {
          return; // Auth is valid, app shell loaded — skip login form entirely
        }
      } catch (err) {
        if (isPageClosedError(err)) {
          throw new Error(
            'loginUser: Page/context/browser was closed (test likely timed out). Increase test.setTimeout.'
          );
        }
        // API login or shell wait failed — fall through to full UI login
      }
    }
    // Auth not valid or expired — clear and proceed to login form
    await clearAuthStorage(page);
  }

  // Navigate to login page for fresh login (forceFreshLogin=true or storageState auth failed)
  if (forceFreshLogin) {
    await clearAuthStorage(page);
  }
  await gotoWithRetry(page, '/login');

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

  // Wait for button to be visible AND enabled (button starts disabled when
  // getInitialIsLoading() finds stale tokens in localStorage during hydration)
  const submitButton = page
    .locator('button[type="submit"]')
    .or(page.locator('button.login-button'));
  await submitButton.waitFor({ state: 'visible', timeout: 5000 });
  // Use function (not string) to avoid CSP unsafe-eval violation on staging
  await page.waitForFunction(
    () => {
      const btn = document.querySelector('button[type="submit"]') as HTMLButtonElement | null;
      return btn && !btn.disabled;
    },
    { timeout: 10000 }
  );

  // Submit form and wait for login API response (60s for Docker API under parallel E2E load)
  // On 429 (rate limit), retry with backoff so E2E suite can complete without flake
  // On 500 (server error), retry - OpenAPI/capabilities may cause transient 500s under parallel load
  // On timeout (API slow under load), fall back to API login
  const loginResponseTimeout = 15000; // Login API should respond within seconds; 15s is generous
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
    await fallbackOrThrow('UI login form timed out (null response)');
    return;
  }
  // On 500: retry up to 2 times (transient server errors from OpenAPI/capabilities under load)
  for (let retries = 0; retries < 2 && loginResponse.status === 500; retries++) {
    await page.waitForTimeout(3000);
    // Clear auth storage before retry — a partial login may have stored tokens,
    // causing getInitialIsLoading() to return true and the submit button to start disabled
    await clearAuthStorage(page);
    await gotoWithRetry(page, '/login');
    await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
    await emailInput.fill(user.email);
    await passwordInput.fill(user.password);
    // Wait for submit button to be enabled (not aria-busy from stale hydration state)
    await submitButton.waitFor({ state: 'visible', timeout: 5000 });
    await page.waitForFunction(
      '(() => { const btn = document.querySelector(\'button[type="submit"]\'); return btn && !btn.disabled; })()',
      { timeout: 10000 }
    );
    const retryResp = await attemptLogin();
    if (retryResp === null) {
      await fallbackOrThrow('UI login timed out after 500 retry');
      return;
    }
    loginResponse = retryResp;
  }
  // On 429: retry UI login up to 2 times, then fall back to API login to avoid rate-limit exhaustion
  for (let retries = 0; retries < 2 && loginResponse.status === 429; retries++) {
    await page.waitForTimeout(15000);
    await clearAuthStorage(page);
    await gotoWithRetry(page, '/login');
    await page.waitForSelector('input#email, input[type="email"]', { timeout: 10000 });
    await emailInput.fill(user.email);
    await passwordInput.fill(user.password);
    await submitButton.waitFor({ state: 'visible', timeout: 5000 });
    await page.waitForFunction(
      '(() => { const btn = document.querySelector(\'button[type="submit"]\'); return btn && !btn.disabled; })()',
      { timeout: 10000 }
    );
    const retryResp = await attemptLogin();
    if (retryResp === null) {
      await fallbackOrThrow('UI login timed out after 429 retry');
      return;
    }
    loginResponse = retryResp;
  }
  if (loginResponse.status === 429) {
    await fallbackOrThrow(`UI login still 429 after retries (rate-limited)`);
    return;
  }
  if (loginResponse.status === 500) {
    // Fallback to API login when UI login returns 500 (e.g. OpenAPI/capabilities under load)
    await fallbackOrThrow(`UI login returned 500`);
    return;
  }
  if (loginResponse.status !== 200) {
    throw new Error(`Login API failed with status ${loginResponse.status}: ${loginResponse.body}`);
  }

  // Wait for navigation away from login page (use expect().toHaveURL for better error messages)
  try {
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 });
  } catch {
    // Check if we're still on login page
    if (page.url().includes('/login')) {
      // Wait for error message or user profile to appear (element-based, not fixed timeout)
      try {
        await page
          .locator('.error-message, .error-display, .app-header')
          .first()
          .waitFor({ state: 'visible', timeout: 5000 })
          .catch(() => {});
      } catch (waitErr) {
        if (isPageClosedError(waitErr)) {
          throw new Error(
            'loginUser: Page/context/browser was closed during auth init. Increase test.setTimeout.'
          );
        }
        throw waitErr;
      }
      // 11.1: access_token is no longer stored in localStorage after UI login (it lives in
      // JS module memory). Check 'user' as the reliable session indicator instead.
      // Poll up to 3s: React's setState → useEffect → localStorage.setItem is async.
      let hasUser = false;
      for (let poll = 0; poll < 6; poll++) {
        hasUser = await page.evaluate(() => !!localStorage.getItem('user'));
        if (hasUser) break;
        await page.waitForTimeout(500);
      }
      if (hasUser) {
        // User profile written but navigation didn't happen - force navigation
        await gotoWithRetry(page, '/');
      } else {
        const errorElement = page.locator('.error-message, .error-display');
        if ((await errorElement.count()) > 0) {
          const errorText = await errorElement.textContent();
          throw new Error(`Login failed: ${errorText}`);
        }
        // Last resort: fall back to API inject instead of hard-failing
        await fallbackOrThrow('Login 200 but user profile not in localStorage after 3s');
      }
    }
  }

  // Wait for page to be ready (domcontentloaded, not networkidle)
  await page.waitForLoadState('domcontentloaded');

  // Wait for auth to be initialized — check that we're not on login page and that
  // localStorage has the user profile. 11.1: access_token is no longer stored in
  // localStorage (it lives in JS module memory); 'user' is the reliable indicator.
  let authInitialized = false;
  for (let attempt = 0; attempt < 30 && !authInitialized; attempt++) {
    try {
      authInitialized = await page.evaluate(() => {
        // 11.1: access_token lives in memory; check only 'user' for session presence.
        return !!localStorage.getItem('user');
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
    // UI login returned 200 but app didn't persist user profile (race under parallel E2E load).
    // Fall back to API login + inject so tests can proceed.
    await fallbackOrThrow(
      'UI login returned 200 but auth state was not initialized within 30s ' +
      '(user profile not in localStorage — possible race condition under parallel E2E load)'
    );
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

  // Verify auth is stable: wait for fetchUser; if token invalid we get redirected to login.
  // Use URL stability check instead of fixed timeout — wait until URL stops changing.
  try {
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
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

  // Phase 11.1 fix: after successful UI login, access_token lives in JS module
  // memory only. When the test later calls page.goto() (which triggers a full page
  // reload in Playwright), JS memory is wiped and initializeAuth() finds no
  // access_token. It attempts to refresh using the stored refresh_token, but that
  // token may have been rotated during login (replay detection) causing a 401 that
  // clears auth state and redirects to /login.
  //
  // Fix: do a supplementary API login and inject access_token into localStorage.
  // initializeAuth() reads access_token from localStorage if present (line 263 of
  // authService.ts), making subsequent page.goto() navigations auth-stable.
  const hasAccessToken = await page.evaluate(
    () => !!localStorage.getItem('access_token')
  );
  if (!hasAccessToken) {
    try {
      const apiAuth = await loginViaApi(user.email, user.password);
      await page.evaluate(
        ({ access_token, refresh_token }) => {
          localStorage.setItem('access_token', access_token);
          if (refresh_token) {
            localStorage.setItem('refresh_token', refresh_token);
          }
        },
        apiAuth
      );
    } catch {
      // API login failed — auth may break on next page.goto() but don't block
      // the current test; the UI login already succeeded.
    }
  }
}
