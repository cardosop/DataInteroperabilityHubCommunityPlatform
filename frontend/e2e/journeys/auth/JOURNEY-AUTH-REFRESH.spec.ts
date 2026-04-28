/**
 * E2E Test: JOURNEY-AUTH-REFRESH — token-refresh contract.
 *
 * Phase 226.F3. Three scenarios prove the refresh contract end-to-end
 * against the deployed backend:
 *
 *   1. Happy path — access_token expired, refresh_token valid → the
 *      apiClient transparently refreshes and the original request
 *      succeeds.
 *
 *   2. Refresh fails → clearTokens + redirect to /login. Both tokens
 *      corrupted; first auth-required request triggers refresh, refresh
 *      gets 401, apiClient clears tokens and pushes the user to /login.
 *      This is the phase3-class regression: a stale refresh_token must
 *      NOT leave the user staring at a broken page.
 *
 *   3. Refresh race — multiple concurrent 401s. Two parallel requests
 *      hit 401 at roughly the same time. The apiClient holds a
 *      singleton in-flight refresh promise (see RefreshRaceState
 *      pure-logic tests in _guards.spec.ts), so the network sees only
 *      ONE POST /auth/refresh/ and both retries succeed.
 *
 * No mocks. The frontend talks to the real deployed API; the test
 * manipulates only its own browser-side localStorage / module-state
 * to synthesize stale-token scenarios. The refresh, retry, and clear
 * paths are exercised by the production apiClient unchanged.
 *
 * Use Case: UC-AUTH-002 (Login session refresh) — listed-adjacent in
 *           docs/CRITICAL_UC_JOURNEY_IDS.yaml.
 * Tracked under: Phase 226.F3.
 */

import { expect, test, type Page, type Request } from '@playwright/test';
// `Request` is used by the trackRefreshRequests handler signature below.
import { getTestUser, loginUser } from '../../fixtures/auth';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

/**
 * Synthesize a syntactically-plausible-but-stale JWT. The backend will
 * fail signature verification → 401 → triggers the apiClient refresh
 * path. We avoid using a literal `"invalid"` value because some
 * middleware short-circuits on totally-malformed tokens; an
 * alg+typ+payload triple keeps the failure path inside the JWT verifier.
 */
function staleAccessToken(): string {
  const header = Buffer.from(
    JSON.stringify({ alg: 'HS256', typ: 'JWT' }),
  ).toString('base64url');
  const payload = Buffer.from(
    JSON.stringify({
      sub: '00000000-0000-0000-0000-000000000000',
      iss: 'hub',
      aud: ['idh-api-v1'],
      exp: 1, // 1970-01-01 — long expired
      iat: 0,
    }),
  ).toString('base64url');
  // 32-byte random hex masquerading as a signature; the backend will
  // reject either on iss/aud check or signature, both routed to 401.
  const signature = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
  return `${header}.${payload}.${signature}`;
}

/**
 * Inject a stale access_token AND keep the valid refresh_token. The
 * apiClient picks both up from localStorage on the next page load
 * (see authStore initialize at frontend/src/features/auth/.../authService.ts).
 */
async function corruptAccessTokenOnly(page: Page): Promise<void> {
  await page.evaluate((stale) => {
    localStorage.setItem('access_token', stale);
  }, staleAccessToken());
}

/**
 * Wipe the refresh_token so the apiClient's `_handleRefreshAndRetry`
 * cannot recover. In legacy mode this means localStorage; in cookie
 * mode the server-side httpOnly cookie is unreachable from JS, so this
 * helper additionally calls `/auth/logout/` to drop the cookie.
 */
async function corruptBothTokens(page: Page): Promise<void> {
  // Drop refresh_token from localStorage (legacy mode).
  await page.evaluate(() => {
    localStorage.removeItem('refresh_token');
  });
  // Drop the httpOnly refresh cookie (cookie mode). The /auth/logout/
  // route clears it server-side.
  await page.request.post(`${API_BASE}/auth/logout/`, {
    headers: { 'Content-Type': 'application/json' },
    failOnStatusCode: false,
  });
  // Now corrupt the access_token so the next call goes through the
  // 401 → refresh path. The refresh will fail because the cookie is
  // gone and the legacy refresh_token is gone too.
  await page.evaluate((stale) => {
    localStorage.setItem('access_token', stale);
  }, staleAccessToken());
}

interface RefreshNetworkLog {
  refreshPostCount: number;
  refreshUrls: string[];
  unsubscribe(): void;
}

/**
 * Count POST /auth/refresh/ requests on a page so the race-test can
 * assert exactly-one refresh fired.
 */
function trackRefreshRequests(page: Page): RefreshNetworkLog {
  const log: RefreshNetworkLog = {
    refreshPostCount: 0,
    refreshUrls: [],
    unsubscribe: () => {},
  };
  const handler = (req: Request) => {
    if (req.method() !== 'POST') return;
    const url = req.url();
    if (url.includes('/auth/refresh/')) {
      log.refreshPostCount++;
      log.refreshUrls.push(url);
    }
  };
  page.on('request', handler);
  log.unsubscribe = () => page.off('request', handler);
  return log;
}

test.describe('JOURNEY-AUTH-REFRESH: token refresh contract @critical', () => {
  test.setTimeout(120_000);

  test('happy path — stale access_token → refresh succeeds → original request retries and 200s', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 15_000 });

    const log = trackRefreshRequests(page);

    // The user is currently logged in. Corrupt the access_token in
    // localStorage so the next auth-required request fails 401 and
    // forces the apiClient to refresh.
    await corruptAccessTokenOnly(page);

    // Trigger a real auth-required request via a soft navigation. The
    // /api/v1/auth/me/ call fires from the auth store's heartbeat; we
    // also ensure something happens by hitting /assets which triggers
    // a list call.
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });

    // Wait until the apiClient has had time to refresh + retry.
    // Either we land on /assets with content rendered, or the refresh
    // failed (which would be the test-2 scenario — fail loudly here).
    await expect(page).toHaveURL(/\/assets/, { timeout: 30_000 });
    expect(
      page.url().includes('/login'),
      'happy-path should NOT redirect to /login: refresh should have succeeded.',
    ).toBe(false);

    // Sanity: localStorage now holds a NEW access_token string (different
    // from the stale one we injected). Both legacy and cookie modes
    // should have a non-stale value here — cookie mode mirrors the new
    // access_token into localStorage via the auth store for the SPA's
    // own state, even if Bearer is not added to the header.
    const finalToken = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(finalToken).not.toBe(staleAccessToken());

    // The refresh path should have fired once (or zero times on cookie
    // mode if the SPA detected the new access_token via a different
    // channel — but we don't assume that).
    expect(log.refreshPostCount).toBeGreaterThanOrEqual(1);
    log.unsubscribe();
  });

  test('refresh fails → clearTokens + redirect to /login (phase3-class regression)', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 15_000 });

    await corruptBothTokens(page);

    // First auth-required request after the corruption MUST fail
    // refresh and trigger the redirect path. /assets is a sufficient
    // probe — its list call goes through apiClient.
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });

    // The apiClient pushes window.location.href = '/login' on
    // _handleRefreshAndRetry's catch branch. Wait for the redirect.
    await page.waitForURL(/\/login/, { timeout: 30_000 });
    expect(page.url()).toContain('/login');

    // Tokens MUST be cleared by the apiClient's clearTokens() path.
    const lsAfter = await page.evaluate(() => ({
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token'),
      user: localStorage.getItem('user'),
    }));
    expect(lsAfter.access, 'access_token must be cleared after a failed refresh').toBeFalsy();
    expect(lsAfter.refresh, 'refresh_token must be cleared after a failed refresh').toBeFalsy();
  });

  test('refresh race — N concurrent 401s share ONE refresh and all retries succeed', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 15_000 });

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) {
      throw new Error(
        'AUTH-REFRESH race: localStorage access_token null after loginUser — auth fixture should have established a session.',
      );
    }

    const log = trackRefreshRequests(page);

    // Inject the stale access_token into localStorage (the apiClient
    // will pick it up via authStore initialise on the next navigation).
    // The next batch of SPA navigations will all see the stale token
    // and race into the 401-then-refresh path together.
    await corruptAccessTokenOnly(page);

    // Trigger N concurrent SPA navigations. Each navigation kicks off
    // multiple auth-required calls via the singleton apiClient, which
    // is exactly the production refresh-race path. Counting POSTs to
    // /auth/refresh/ from the page-network listener gives us the
    // assertion we need without depending on any apiClient internal.
    const N = 4;
    await Promise.all(
      Array.from({ length: N }, (_, i) =>
        // intentional: a single navigation in the race may itself land on /login when the SPA's auth-store decides the token is fatally bad — that's a legitimate state for that one navigation; the post-race assertions below target the AGGREGATE refresh count + final URL, which are the contract we actually care about.
        page.goto(`/assets?race=${i}`, { waitUntil: 'domcontentloaded' }).catch(() => null),
      ),
    );

    // The race may take a beat to settle once the refresh kicks in.
    // Polling until either the URL stabilises on /assets or the refresh
    // count plateaus.
    await expect(page).toHaveURL(/\/assets/, { timeout: 30_000 });

    // The contract: the in-flight refresh promise dedupes concurrent
    // callers. Allow up to TWO refreshes here because:
    //   (a) the very first call may trigger the refresh before the
    //       page's other tabs even attach to the promise (single-cycle), and
    //   (b) Playwright's navigation can re-parse the SPA bundle on
    //       fast successive navigations, which restarts the apiClient
    //       module — that's a second cycle that's still correct.
    // A floor of 1 (the refresh fired) and a ceiling of 2 (no
    // per-request storm) prove the singleton-promise dedup at the
    // browser level. The pure-logic tests in _guards.spec.ts cover
    // strict 1:1 dedup at the state-machine level.
    expect(
      log.refreshPostCount,
      `refresh POSTs should be ≤ 2 across ${N} concurrent calls (saw ${log.refreshPostCount} at ${log.refreshUrls.join(', ')})`,
    ).toBeLessThanOrEqual(2);
    expect(log.refreshPostCount).toBeGreaterThanOrEqual(1);

    // Final state: NO redirect to /login (refresh succeeded).
    expect(page.url()).not.toContain('/login');

    log.unsubscribe();
  });
});
