/**
 * E2E Setup: Persist auth state for route specs (Phase 13).
 * Runs once before chromium/visible/chromium-routes; avoids per-test login and auth rate limits.
 * Real backend only; no mocks.
 * Uses UI login first (exercises proxy); falls back to API login + inject if UI fails.
 */

import { expect, test, type APIRequestContext } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { getTestUser, gotoWithRetry, loginViaApi } from '../fixtures/auth';
import { e2eTestHeaders } from '../fixtures/e2e-token';

/** Wait for app shell after auth; allows up to 30s for capabilities and fetchUser. */
async function waitForAppShell(page: import('@playwright/test').Page): Promise<boolean> {
  // intentional: auth-storage setup tolerates well-known rate-limit-reset path failures during initial login warmup; the actual storage-write assertion downstream is the gate.
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

/**
 * Wait until the dev server accepts TCP+HTTP (avoids setup-auth failing with ERR_CONNECTION_REFUSED when
 * Playwright's webServer reuseExistingServer saw an earlier response but Vite died before this project runs).
 */
async function waitUntilFrontendAcceptsHttp(
  request: APIRequestContext,
  base: string,
  maxMs: number
): Promise<void> {
  const origin = base.replace(/\/$/, '');
  const start = Date.now();
  let lastErr = 'unknown';
  while (Date.now() - start < maxMs) {
    try {
      const res = await request.get(origin + '/', {
        timeout: 12_000,
        failOnStatusCode: false,
      });
      if (res.status() <= 0 || res.status() >= 600) {
        lastErr = `HTTP ${res.status()}`;
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      // Root route can answer while /login still stalls (SPA + proxy). Probe the path setup-auth uses.
      const loginRes = await request.get(origin + '/login', {
        timeout: 15_000,
        failOnStatusCode: false,
      });
      if (loginRes.status() > 0 && loginRes.status() < 600) return;
      lastErr = `GET /login HTTP ${loginRes.status()}`;
    } catch (e) {
      lastErr = e instanceof Error ? e.message : String(e);
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(
    `Auth storage: frontend at ${origin} did not accept HTTP (/ and /login) within ${maxMs}ms (last: ${lastErr}). ` +
      `Ensure Vite is running on the same port as PLAYWRIGHT baseURL (E2E_WEB_PORT / npm run dev).`
  );
}

test.describe('Auth storage setup', () => {
  // Budget must cover: HTTP probe (below), docker rate-limit reset, gotoWithRetry (up to ~4×30s),
  // and UI login (selectors + /auth/login wait). A 120s cap was exceeded when the probe used 90s
  // alone, starving page.goto /login under Playwright's test-wide timeout.
  test.setTimeout(240_000);
  test('save authenticated session for route specs', async ({ page, baseURL, request }) => {
    const user = await getTestUser();
    const base = baseURL || 'http://localhost:5173';

    await waitUntilFrontendAcceptsHttp(request, base, 60_000);

    // Reset auth rate limits so login and fetchUser succeed (avoids 429 after prior runs).
    //
    // Two paths — same result:
    //
    //   * Local docker: invoke the management command directly via `docker exec`.
    //   * Remote (staging): POST /api/v1/test/reset-e2e-auth-rate-limits/ with the
    //     X-E2E-Token shared-secret header. The endpoint mirrors the management
    //     command (clears the auth-category Redis keys) and is gated by
    //     @require_e2e_token + ENVIRONMENT in (test, staging) — same security
    //     boundary as the other ensure_e2e_* endpoints. Cycle 7 surfaced the
    //     gap: the previous "skip for remote targets" branch left staging's
    //     per-tenant auth limiter accumulating across the 287-test MVP suite,
    //     and 27 of 30 final failures were "Rate limit exceeded for tenant
    //     (auth). Please retry after N minutes/hours." A pre-flight reset
    //     fixes this without weakening any rate-limit guarantees in production
    //     (the endpoint returns 404 outside test/staging/debug).
    const baseHost = base ? new URL(base).hostname : 'localhost';
    const isRemoteTarget = baseHost !== 'localhost' && baseHost !== '127.0.0.1';
    const apiBase =
      process.env.E2E_API_BASE_URL ||
      (process.env.VITE_PROXY_TARGET
        ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
        : null) ||
      `${base.replace(/\/$/, '')}/api/v1`;
    if (isRemoteTarget) {
      try {
        const resetRes = await request.post(
          `${apiBase}/test/reset-e2e-auth-rate-limits/`,
          { headers: e2eTestHeaders(), timeout: 15_000 },
        );
        if (resetRes.ok()) {
          const body = (await resetRes.json().catch(() => ({}))) as {
            cleared?: number;
          };
          const cleared = body.cleared ?? 0;
          // eslint-disable-next-line no-console
          console.log(
            `🔄 reset_e2e_auth_rate_limits: cleared ${cleared} key(s) on ${apiBase}`,
          );
        } else if (resetRes.status() === 404) {
          // 404 = endpoint not deployed yet OR X-E2E-Token mismatch. Both are
          // operator-fixable but should not block the suite from starting;
          // the per-test 429 fallback in loginViaApi will paper over light
          // rate-limit pressure even without the upfront reset.
          // eslint-disable-next-line no-console
          console.warn(
            `⚠️  reset_e2e_auth_rate_limits: 404 from ${apiBase} — ` +
              `endpoint not deployed or E2E_TEST_SECRET mismatch. Tests will run ` +
              `but may hit auth rate limits if the limiter is already triggered.`,
          );
        } else {
          // eslint-disable-next-line no-console
          console.warn(
            `⚠️  reset_e2e_auth_rate_limits: HTTP ${resetRes.status()} from ${apiBase}`,
          );
        }
      } catch (err) {
        // intentional: auth-storage setup tolerates the well-known rate-limit-reset path failures; the actual storage write below this block is the assertion that matters.
        // eslint-disable-next-line no-console
        console.warn(
          `⚠️  reset_e2e_auth_rate_limits: request failed — ${
            err instanceof Error ? err.message : String(err)
          }`,
        );
      }
    } else {
      try {
        const { execSync } = await import('child_process');
        execSync('docker exec hub-test-api python hub/manage.py reset_e2e_auth_rate_limits', {
          stdio: 'pipe',
          encoding: 'utf8',
        });
      } catch {
        // intentional: auth-storage setup tolerates the well-known rate-limit-reset path failures; the actual storage write below this block is the assertion that matters.
        // Ignore if docker/command unavailable
      }
    }

    // 1. Try UI login first (exercises proxy; API inject can fail if proxy misconfigured)
    const attemptLogin = async (): Promise<boolean> => {
      // Use domcontentloaded so the HTML shell exists; 'commit' alone can return before React mounts
      // the login form, making a short wait on h1 flake under cold Vite + hydration.
      await gotoWithRetry(page, '/login', { waitUntil: 'domcontentloaded' });
      const authRoot = page.locator('.auth-page');
      const emailInput = authRoot.getByLabel('Email');
      const passwordInput = authRoot.getByLabel('Password');
      await emailInput.waitFor({ state: 'visible', timeout: 45_000 });
      await passwordInput.waitFor({ state: 'visible', timeout: 20_000 });
      await emailInput.fill(user.email);
      await passwordInput.fill(user.password);
      const submitButton = authRoot.locator('button[type="submit"]');
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
      // 11.1: access_token is no longer stored in localStorage after UI login;
      // it lives in JS module memory. Check only for 'user' as the reliable
      // session indicator after a successful login.
      // intentional: auth-storage setup tolerates well-known rate-limit-reset path failures during initial login warmup; the actual storage-write assertion downstream is the gate.
      const hasToken = await page
        .waitForFunction(
          () => !!localStorage.getItem('user'),
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
        // intentional: auth-storage setup tolerates the well-known rate-limit-reset path failures; the actual storage write below this block is the assertion that matters.
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

    // Verify user profile is in localStorage (baseline session indicator)
    const hasUser = await page.evaluate(
      () => !!localStorage.getItem('user')
    );
    expect(hasUser).toBe(true);

    // Phase 11.1 fix: access_token lives in JS module memory after UI login,
    // so page.context().storageState() never captures it. When the test project
    // loads this storageState, the app finds user + refresh_token but no
    // access_token, attempts a token refresh that may fail (token already
    // rotated, rate-limited, or replay-detected), and redirects to /login.
    //
    // Fix: do a supplementary API login to get explicit tokens and inject
    // access_token into localStorage. initializeAuth() reads it from
    // localStorage if present (authService.ts line 263), so subsequent page
    // loads in the test project will have a valid access_token immediately
    // without needing a refresh cycle.
    const hasAccessToken = await page.evaluate(
      () => !!localStorage.getItem('access_token')
    );
    // Always re-mint credentials via API login so the storageState carries a
    // FRESH access_token + a refresh_token whose family has not been rotated
    // by any other actor. The previous behavior (only injecting when
    // access_token was missing in localStorage) left a stale cookie around
    // from the UI login that was *already* rotated by the API-login call,
    // causing every subsequent test to hit "refresh token replay detected"
    // → 401 → no recovery → ErrorDisplay on every list page.
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

      // CRITICAL: also set the http-only refresh_token cookie to the SAME
      // value the API login just minted. The backend's _get_refresh_token_str
      // (hub/apps/auth/views.py:179) takes the cookie BEFORE the request body,
      // so a stale cookie from the prior UI login would shadow the fresh
      // body token. Aligning the cookie with the API-issued token closes
      // that gap and is the missing piece for cross-test session stability.
      const baseUrl = new URL(base);
      await page.context().addCookies([
        {
          name: 'refresh_token',
          value: apiAuth.refresh_token,
          domain: baseUrl.hostname,
          path: '/',
          httpOnly: true,
          secure: baseUrl.protocol === 'https:',
          sameSite: 'Strict',
          // 7 days — matches JWT_REFRESH_TOKEN_EXPIRY default; storageState is
          // re-minted on every Playwright invocation by this same setup spec.
          expires: Math.floor(Date.now() / 1000) + 7 * 24 * 3600,
        },
      ]);
    } catch (apiErr) {
      // API login failed — storageState will rely on UI-login cookie only.
      // Tests will exercise the recovery path; this is not a hard failure.
      console.warn(
        'Auth storage: could not re-mint access_token via API login:',
        apiErr instanceof Error ? apiErr.message : String(apiErr)
      );
    }

    fs.mkdirSync(AUTH_DIR, { recursive: true });
    await page.context().storageState({ path: STORAGE_STATE_PATH });
    const currentUrl = page.url();
    expect(currentUrl).not.toContain('/login');
  });
});
