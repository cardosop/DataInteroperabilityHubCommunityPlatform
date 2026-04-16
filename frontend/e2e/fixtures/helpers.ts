/**
 * E2E Test Helpers
 * Reusable utilities for E2E tests across all journeys, personas, use cases, and features
 */

import { Page, expect, test } from '@playwright/test';
import { getTestUser, gotoWithRetry, loginUser, loginViaApi, type TestUser } from './auth';

export { isBenignConsoleError } from './console-utils';

/**
 * Inject fresh auth tokens into localStorage + httpOnly cookie before a page.goto().
 * Full-page navigation resets the JS context, losing in-memory auth tokens.
 * By writing to localStorage first, authStore.initialize() picks them up on reload.
 */
async function injectTokensBeforeGotoForUser(page: Page, user?: TestUser): Promise<void> {
  try {
    const u = user ?? (await getTestUser());
    const apiAuth = await loginViaApi(u.email, u.password);
    await page.evaluate(
      ({ access_token, refresh_token, usr }) => {
        localStorage.setItem('access_token', access_token);
        if (refresh_token) localStorage.setItem('refresh_token', refresh_token);
        localStorage.setItem('user', JSON.stringify(usr));
      },
      { access_token: apiAuth.access_token, refresh_token: apiAuth.refresh_token, usr: apiAuth.user }
    );
    if (apiAuth.refresh_token) {
      const pageUrl = page.url();
      const cookieDomain = pageUrl.startsWith('http') ? new URL(pageUrl).hostname : 'localhost';
      await page.context().addCookies([{
        name: 'refresh_token',
        value: apiAuth.refresh_token,
        domain: cookieDomain,
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Strict' as const,
      }]).catch(() => {});
    }
  } catch {
    // API login may fail under load; continue with existing auth
  }
}

/**
 * Check if page shows login prompt (email input, login link, or Sign in text).
 * Use after unauthenticated access to protected routes that may show inline login.
 */
export async function hasLoginPrompt(page: Page): Promise<boolean> {
  const hasEmail = (await page.locator('input#email').count()) > 0;
  const hasLoginLink = (await page.locator('[href*="/login"]').count()) > 0;
  const hasSignInText = (await page.getByText(/Sign in/i).count()) > 0;
  return hasEmail || hasLoginLink || hasSignInText;
}

/**
 * After `goto` to a role-gated path, wait for SPA to finish (403, login, MVP
 * coming-soon/unavailable, or navigated off the forbidden prefix).
 * Do not use `waitForURL(/...admin.../)` — it resolves immediately while still on /admin.
 *
 * Phase 213.I.8 — after Phase 213.I the redirect is synchronous (<100ms)
 * because ProtectedRoute hydrates from localStorage instead of waiting for
 * /auth/me/. The 25s budget is intentionally over-spec'd as a safety net
 * against any future regression that re-introduces blocking init.
 * DO NOT lower the budget.
 */
/**
 * Returns the resolved pathname so callers can distinguish RBAC denial
 * (/403, /coming-soon, /unavailable) from auth expiry (/login).
 *
 * Phase 220 audit: `/login` redirect means the session expired, NOT
 * that the role was denied. Callers should `test.skip()` on `/login`
 * to avoid false positives where auth expiry is counted as RBAC working.
 */
export async function waitForRoleGuardResolved(
  page: Page,
  options: { forbiddenPathPrefix: string; timeout?: number }
): Promise<string> {
  const { forbiddenPathPrefix, timeout = 25000 } = options;
  await page.waitForFunction(
    (prefix: string) => {
      const path = window.location.pathname;
      if (path.includes('/403')) return true;
      if (path.includes('/login')) return true;
      if (path.startsWith('/coming-soon')) return true;
      if (path.startsWith('/unavailable')) return true;
      if (!path.startsWith(prefix)) return true;
      return false;
    },
    forbiddenPathPrefix,
    { timeout }
  );
  return new URL(page.url()).pathname;
}

/**
 * Wait for API response with retry logic
 */
export async function waitForApiResponse(
  page: Page,
  urlPattern: string | RegExp,
  options: {
    timeout?: number;
    status?: number | number[];
    retries?: number;
    retryDelay?: number;
  } = {}
): Promise<Response> {
  const { timeout = 30000, status, retries = 3, retryDelay = 2000 } = options;

  const statusArray = status ? (Array.isArray(status) ? status : [status]) : undefined;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await page.waitForResponse(
        (resp) => {
          const urlMatch =
            typeof urlPattern === 'string'
              ? resp.url().includes(urlPattern)
              : urlPattern.test(resp.url());

          if (!urlMatch) return false;

          if (statusArray) {
            return statusArray.includes(resp.status());
          }

          return resp.status() < 500; // Don't wait for 5xx errors
        },
        { timeout: attempt === 0 ? timeout : timeout * (attempt + 1) }
      );

      // Check if status matches (if specified)
      if (statusArray && !statusArray.includes(response.status())) {
        if (attempt < retries) {
          await page.waitForTimeout(retryDelay);
          continue;
        }
        throw new Error(
          `API response status ${response.status()} does not match expected ${statusArray.join(' or ')}`
        );
      }

      return response;
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      await page.waitForTimeout(retryDelay);
    }
  }

  throw new Error(`Failed to get API response after ${retries + 1} attempts`);
}

/**
 * Wait for element with retry logic
 */
export async function waitForElement(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
    state?: 'attached' | 'detached' | 'visible' | 'hidden';
    retries?: number;
    retryDelay?: number;
  } = {}
): Promise<void> {
  const { timeout = 10000, state = 'visible', retries = 3, retryDelay = 1000 } = options;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      await page.waitForSelector(selector, {
        timeout: attempt === 0 ? timeout : timeout * (attempt + 1),
        state,
      });
      return;
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      await page.waitForTimeout(retryDelay);
    }
  }
}

/**
 * Fill form field with retry logic
 */
export async function fillField(
  page: Page,
  selector: string,
  value: string,
  options: {
    timeout?: number;
    clear?: boolean;
  } = {}
): Promise<void> {
  const { timeout = 10000, clear = true } = options;

  await waitForElement(page, selector, { timeout, state: 'visible' });

  const field = page.locator(selector);

  if (clear) {
    await field.clear();
  }

  await field.fill(value);

  // Verify value was set
  const actualValue = await field.inputValue();
  if (actualValue !== value) {
    throw new Error(`Failed to set field value: expected "${value}", got "${actualValue}"`);
  }
}

/**
 * Click element with retry logic
 */
export async function clickElement(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
    force?: boolean;
    retries?: number;
  } = {}
): Promise<void> {
  const { timeout = 10000, force = false, retries = 3 } = options;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      await waitForElement(page, selector, { timeout, state: 'visible' });
      const element = page.locator(selector);

      if (force) {
        await element.click({ force: true });
      } else {
        await element.click();
      }

      return;
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      await page.waitForTimeout(1000);
    }
  }
}

/**
 * Wait for navigation with timeout
 */
export async function waitForNavigation(
  page: Page,
  urlPattern: string | RegExp,
  options: {
    timeout?: number;
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle';
  } = {}
): Promise<void> {
  const { timeout = 10000, waitUntil = 'domcontentloaded' } = options;

  await page.waitForURL(
    (url) => {
      if (typeof urlPattern === 'string') {
        return url.pathname.includes(urlPattern) || url.href.includes(urlPattern);
      }
      return urlPattern.test(url.pathname) || urlPattern.test(url.href);
    },
    { timeout, waitUntil }
  );
}

/**
 * Generate unique identifier for test data
 */
export function generateUniqueId(prefix = 'e2e'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Generate unique email for test users
 */
export function generateUniqueEmail(prefix = 'e2e'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}@example.com`;
}

/**
 * Detect whether the test is targeting a remote API (deployed staging/production)
 * vs a local docker-compose backend.
 *
 * Used to skip tests that require backend role assignment via Django management
 * commands (e.g. ensure_e2e_user_roles), which is unavailable on remote APIs.
 * The persona RBAC tests need users with TENANT_ADMIN/PLATFORM_ADMIN/AUDITOR
 * roles assigned, which the API registration endpoint cannot do.
 */
export function isRemoteApiTarget(): boolean {
  const apiBase =
    process.env.E2E_API_BASE_URL ||
    process.env.PLAYWRIGHT_BASE_URL ||
    '';
  if (!apiBase) return false;
  try {
    const h = new URL(apiBase).hostname;
    return h !== 'localhost' && h !== '127.0.0.1';
  } catch {
    return false;
  }
}

/**
 * Skip the current test/describe block when targeting a remote API.
 * Use for tests that depend on backend state mutations only possible via
 * docker exec / kubectl exec (e.g. role assignment, DB seeding).
 */
export function skipIfRemoteApi(test: { skip(condition: boolean, reason: string): void }, reason: string): void {
  test.skip(
    isRemoteApiTarget(),
    `Skipped on remote API: ${reason}. Run locally with docker-compose for full coverage.`
  );
}

/**
 * Wait for app main content (no loading spinner). Use after goto for any protected route.
 * Also treats .loading-spinner-container as loading so list pages that use LoadingSpinner are covered.
 * Fails with a clear message if redirected to login (auth may have failed or expired).
 * Default timeout 30s to allow for slow capabilities/API under parallel E2E load.
 *
 * @param options.acceptRedirectToLogin - When true, treat redirect to login as success (for tests
 *   that expect 403/redirect, e.g. "governance without role shows 403 or redirect").
 */
export async function waitForAppMainReady(
  page: Page,
  options: { timeout?: number; contentSelector?: string; acceptRedirectToLogin?: boolean } = {}
): Promise<void> {
  const { timeout = 30000, contentSelector, acceptRedirectToLogin = false } = options;
  await page.waitForLoadState('domcontentloaded');

  // Grace period: auth may still be initializing; avoid false failure on slow fetchUser/capabilities.
  // 12s allows for parallel E2E load where backend/capabilities can be slow.
  const authGraceMs = 12000;
  const graceDeadline = Date.now() + authGraceMs;

  // Poll: if we end up on login after grace period, fail (or accept if acceptRedirectToLogin)
  const checkInterval = 500;
  const start = Date.now();

  const safeWait = async (ms: number): Promise<void> => {
    try {
      await page.waitForTimeout(ms);
    } catch (e) {
      const msg = String(e);
      if (/Target page, context or browser has been closed|page has been closed/i.test(msg)) {
        throw new Error(
          `waitForAppMainReady: Test timed out during poll (page closed). Increase test.setTimeout. URL: ${page.url()}`
        );
      }
      throw e;
    }
  };

  while (Date.now() - start < timeout) {
    let url: string;
    try {
      url = page.url();
    } catch (e) {
      const msg = String(e);
      if (/Target page, context or browser has been closed|page has been closed/i.test(msg)) {
        throw new Error(
          'waitForAppMainReady: Test timed out (page closed). Increase test.setTimeout.'
        );
      }
      throw e;
    }
    if (url.includes('/login')) {
      if (Date.now() < graceDeadline) {
        await safeWait(checkInterval);
        continue;
      }
      if (acceptRedirectToLogin) {
        return;
      }
      throw new Error(
        'waitForAppMainReady: Redirected to login; auth may have failed or expired. ' +
          'Ensure loginUser completed successfully before calling this helper.'
      );
    }
    // /403, /unavailable, and /coming-soon are top-level routes without .app-main; page is ready when we reach them
    if (url.includes('/403') || url.includes('/unavailable') || url.includes('/coming-soon')) {
      await safeWait(500);
      return;
    }
    // CapabilityRoute renders .unavailable-page in-place (at the current URL, not /unavailable)
    // when the capability is disabled. This is a terminal state — no .app-main will ever appear.
    const hasUnavailablePage = await page.locator('.unavailable-page').count();
    if (hasUnavailablePage > 0) {
      await safeWait(500);
      return;
    }
    // SPA catch-all NotFoundPage renders with .not-found-page class and role="alert".
    // This is a terminal state for routes that don't exist in the router.
    const has404Page = (await page.locator('.not-found-page').count().catch(() => 0)) > 0;
    if (has404Page) {
      await safeWait(500);
      return;
    }
    // Intentional fallback: evaluate may fail if context destroyed; treat as not ready, continue polling
    const ready = await page
      .evaluate((sel: string | undefined) => {
        const main = document.querySelector('.app-main');
        if (!main) return false;
        // When route-specific selector provided, wait for it to appear inside .app-main
        if (sel) {
          const el = main.querySelector(sel);
          if (el) return true;
          return false;
        }
        // No contentSelector: wait for loading indicators inside .app-main to disappear.
        // This ensures API calls have completed before the test proceeds.
        // Covers both LoadingSpinner component and ListPageSkeleton placeholder.
        const loading =
          main.querySelector('.loading-spinner') ||
          main.querySelector('.loading-spinner-container') ||
          main.querySelector('[data-testid="skeleton-row"]') ||
          main.querySelector('.skeleton');
        if (loading) return false;
        return true;
      }, contentSelector)
      .catch(() => false);
    if (ready) {
      await safeWait(1000);
      return;
    }
    await safeWait(checkInterval);
  }

  // Main loop timed out. The auth store has a 60s safety timeout that races with our loop.
  // When both are ~60s, the auth store may resolve (redirect to /login or show .app-main)
  // in the same frame our loop ends. Wait up to 20s more for the page to reach a terminal
  // state — this covers the auth safety timeout race condition without blindly increasing
  // the main loop timeout.
  const POST_TIMEOUT_GRACE_MS = 5000;
  const graceStart = Date.now();
  while (Date.now() - graceStart < POST_TIMEOUT_GRACE_MS) {
    const currentUrl = page.url();
    if (currentUrl.includes('/login')) {
      if (acceptRedirectToLogin) return;
      throw new Error(
        'waitForAppMainReady: Redirected to login after auth safety timeout.'
      );
    }
    if (
      currentUrl.includes('/403') ||
      currentUrl.includes('/unavailable') ||
      currentUrl.includes('/coming-soon')
    )
      return;
    if ((await page.locator('.app-main').count()) > 0) return;
    if ((await page.locator('.unavailable-page').count()) > 0) return;
    // Still in auth loading state — keep waiting
    await safeWait(500);
  }

  throw new Error(
    `waitForAppMainReady: .app-main not ready within ${timeout + POST_TIMEOUT_GRACE_MS}ms. ` +
      `URL: ${page.url()}`
  );
}

/**
 * Routes that fetch list/detail data; wait for API response before waitForAppMainReady.
 * Prevents timeout when API is slow under E2E load (e.g. contracts list after asset/dataset creation).
 * Returns a promise to await after the nav action that triggers the fetch.
 */
const ROUTES_WITH_DATA_API: Record<string, string> = {
  '/contracts': 'contracts',
  '/odps': 'contracts',
  '/assets': 'assets',
  '/datasets': 'datasets',
  '/integrations/connections': 'marketplace/connections',
  '/integrations/mappings': 'marketplace/mappings',
  '/integrations/sync-jobs': 'marketplace/sync',
  '/settings/api-keys': 'auth/api-keys',
  '/settings/sessions': 'auth/sessions',
  '/scheduled-ingestions': 'scheduled-ingestions',
  '/scheduled-exports': 'scheduled-exports',
  '/marketplace': 'marketplace/listings',
  '/marketplace/orders': 'marketplace/orders',
  '/marketplace/entitlements': 'marketplace/entitlements',
  '/jobs': 'jobs',
  '/virtualization': 'virtualization',
  '/mesh': 'mesh',
  '/dq': 'dq',
  '/compliance': 'compliance',
  '/webhooks': 'webhooks',
  '/files': 'files',
  '/audit': 'audit/audit-events',
  '/admin': 'users',
  '/governance': 'governance',
  '/governance/retention': 'governance/retention-policies',
};

/** Routes that don't fetch list data on load; skip API wait to avoid timeout. */
const ROUTES_WITHOUT_LIST_API = ['/mesh/create', '/marketplace/publish'];

/** Get API pattern for route; supports exact match and prefix (e.g. /assets/123 -> assets). */
function getRouteApiPattern(route: string): string | undefined {
  if (ROUTES_WITHOUT_LIST_API.includes(route)) return undefined;
  const exact = ROUTES_WITH_DATA_API[route];
  if (exact) return exact;
  const prefixes = Object.keys(ROUTES_WITH_DATA_API)
    .filter((r) => r !== '/' && route.startsWith(r + '/'))
    .sort((a, b) => b.length - a.length);
  return prefixes.length > 0 ? ROUTES_WITH_DATA_API[prefixes[0]] : undefined;
}

function startRouteDataApiWait(
  page: Page,
  route: string,
  timeout: number
): Promise<void> | undefined {
  const basePattern = getRouteApiPattern(route);
  if (!basePattern) return undefined;
  // Intentional fallback: API may not fire or may timeout; caller continues without blocking
  return page
    .waitForResponse(
      (r) =>
        r.request().method() === 'GET' && r.url().includes(basePattern),
      { timeout: Math.min(timeout, 90000) }
    )
    .then(() => {})
    .catch(() => undefined);
}

/** Sidebar nav link text for routes (client-side nav avoids full-reload auth race) */
const ROUTE_NAV_LABELS: Record<string, string> = {
  '/assets': 'Assets',
  '/datasets': 'Datasets',
  '/contracts': 'Contracts',
  '/marketplace': 'Marketplace',
  '/search': 'Search',
  '/virtualization': 'Virtualization',
  '/communities': 'Communities',
  '/ai/search': 'AI Search',
  '/developer': 'Developer',
  '/baas': 'BaaS',
  '/ml': 'ML',
  '/scheduled-ingestions': 'Scheduled Ingestion',
  '/dq': 'Data Quality',
  '/compliance': 'Compliance',
  '/integrations/connections': 'Integrations',
  '/jobs': 'Jobs',
  '/mesh': 'Data Mesh',
  '/odps': 'ODPS',
  '/governance': 'Governance',
  '/files': 'Files',
  '/observability': 'Observability',
  '/webhooks': 'Webhooks',
  '/audit': 'Audit',
  '/admin': 'Admin',
  '/semantic': 'Semantic',
  '/transformation': 'Transformation',
  '/': 'Home',
};

/**
 * Route-specific content selectors for waitForAppMainReady.
 * Matches page shell (including loading state) so we don't block on slow APIs.
 */
const ROUTE_CONTENT_SELECTORS: Record<string, string> = {
  '/audit': '.audit-event-list-page, .audit-list-filters, .empty-state, .error-display',
  '/mesh': '.mesh-domain-list-page, .error-display, .empty-state',
  '/mesh/create': '.mesh-domain-create-page, .error-display',
  '/mesh/topology': '.topology-visualization, .error-display',
  '/contracts': '.contract-list-page, .empty-state, .error-display',
  '/odps': '.odps-list-page, .odps-empty-state, .error-display, #email',
  // No .loading-spinner-container: CommunitiesTab shows LoadingSpinner until API returns; matching it
  // would signal "ready" before .communities-tab renders.
  '/communities':
    '.communities-page, .communities-tab, .unavailable-page, .error-display, .empty-state, .app-main',
  '/compliance':
    '.compliance-run-list-page, .empty-state, .error-display, .unavailable-page, #email',
  '/assets': '.asset-list-page, .empty-state, .error-display',
  '/dq': '.dq-run-list-page, .empty-state, .error-display, #email',
  '/webhooks':
    '.webhook-list-page, .empty-state, .error-display',
  '/search': '.search-page, .loading-spinner-container, .error-display, .app-main',
  '/ai/search':
    '.ai-search-page, .unavailable-page, .loading-spinner-container, .error-display, .app-main',
  '/settings/sessions':
    '.session-list-page, .session-list-table, .session-list-empty, .error-display, h1',
  '/settings/api-keys':
    '.auth-api-key-list-page, .unavailable-page, .error-display, h1',
  '/observability':
    '.observability-page, [data-testid="observability-page"], .loading-spinner-container, .error-display, .unavailable-page',
  '/developer': '.developer-portal-page, .developer-page, .unavailable-page, .loading-spinner-container, .app-main',
  '/virtualization':
    '.virtual-dataset-list-page, .virtual-dataset-list-header, .empty-state, .error-display',
  '/baas': '.baas-page, .unavailable-page, .loading-spinner-container, .app-main',
  '/ml': '.ml-page, .unavailable-page, .loading-spinner-container, .app-main',
  '/integrations/connections':
    '.connection-list-page, .marketplace-connection-list-page, .empty-state, .error-display, h1',
  '/jobs':
    '.job-list-page, .empty-state, .error-display, h1',
  '/scheduled-ingestions':
    '.scheduled-ingestion-list-page, [data-testid="scheduled-ingestion-list-page"], .empty-state, .error-display, h1',
  '/ai/schema-matching':
    '[data-testid="schema-matching-page"], .schema-matching-page, .unavailable-page, h1',
  '/files':
    '.file-list-page, .empty-state, .error-display, h1',
  '/datasets/create':
    '.dataset-create-page, .file-upload, .loading-spinner-container, form, h1',
  '/scheduled-exports':
    '.scheduled-export-list-page, .empty-state, .error-display, h1',
  // No .loading-spinner-container: lazy Suspense uses LoadingSpinner first, then ListPageSkeleton
  // without listing shells; matching the spinner would make "ready" true too early.
  '/marketplace':
    '[data-testid="listing-list-page"], .listing-list-page, .listing-list-grid, .empty-state, .error-display',
  '/marketplace/orders':
    '.order-list-page, .empty-state, .error-display',
  '/marketplace/entitlements':
    '.entitlement-list-page, .empty-state, .error-display',
  '/marketplace/publish':
    '.listing-publish-page, .listing-publish-form, form, h1',
  '/governance':
    '.governance-access-request-list-page, .governance-create-page, .error-display, h1',
  '/semantic':
    '[data-testid="semantic-page"], .semantic-page, .unavailable-page, .error-display, .app-main',
  '/transformation':
    '.transformation-pipeline-list-page, .unavailable-page, .error-display, .app-main',
  '/integrations/connections/create':
    '.marketplace-connection-create-page, .connection-create-page, .error-display, .loading-spinner-container, form',
};

/**
 * Content selectors for paths not in ROUTE_CONTENT_SELECTORS (detail/edit URLs).
 * Keeps loginAndNavigateToRoute + waitForAppMainReady stable without per-spec overrides.
 */
function resolveRouteContentSelector(route: string, override?: string): string | undefined {
  if (override) return override;
  if (ROUTE_CONTENT_SELECTORS[route]) return ROUTE_CONTENT_SELECTORS[route];
  if (/^\/marketplace\/listings\/[^/]+$/.test(route)) {
    return '.listing-detail-page, .listing-detail-main, .error-display';
  }
  if (/^\/marketplace\/entitlements\/[^/]+$/.test(route)) {
    return '.entitlement-detail-page, .entitlement-detail-main, .error-display';
  }
  if (/^\/virtualization\/create$/.test(route)) {
    return '.virtual-dataset-create-page, .error-display, form, h1';
  }
  if (/^\/virtualization\/[^/]+$/.test(route)) {
    return '.virtual-dataset-detail-page, .error-display';
  }
  if (/^\/mesh\/create$/.test(route)) {
    return '.mesh-domain-create-page, .error-display, form';
  }
  if (/^\/mesh\/[^/]+$/.test(route) && !route.startsWith('/mesh/topology')) {
    return '.mesh-domain-detail-page, .error-display';
  }
  if (/^\/transformation\/pipelines\/[^/]+$/.test(route)) {
    return '.transformation-detail-page, .unavailable-page, .error-display';
  }
  if (/^\/jobs\/[^/]+$/.test(route)) {
    return '.job-detail-page, .error-display';
  }
  if (
    /^\/integrations\/connections\/[^/]+$/.test(route) &&
    route !== '/integrations/connections/create'
  ) {
    return '.marketplace-connection-detail-page, .error-display';
  }
  if (route === '/odps/upload') {
    return '.odps-upload-page, .error-display, form, h1';
  }
  if (/^\/odps\/[^/]+$/.test(route)) {
    return '.odps-detail-page, .error-display';
  }
  if (/^\/dq\/runs\/[^/]+$/.test(route)) {
    return '.dq-run-detail-page, .error-display';
  }
  if (/^\/compliance\/runs\/[^/]+$/.test(route)) {
    return '.compliance-run-detail-page, .error-display';
  }
  if (/^\/scheduled-ingestions\/[^/]+$/.test(route)) {
    return '[data-testid="scheduled-ingestion-detail-page"], .scheduled-ingestion-detail-page, .error-display';
  }
  if (/^\/contracts\/[^/]+\/edit$/.test(route)) {
    return '.contract-editor-page, .error-display';
  }
  if (/^\/contracts\/[^/]+\/link-odps$/.test(route)) {
    return '.odps-link-page, .error-display';
  }
  return undefined;
}

/**
 * Login, navigate to a protected route, and wait for app main ready.
 * Uses loginUser then client-side nav via sidebar (or in-page links) to avoid full-reload auth race.
 *
 * @param options.acceptRedirectToLogin - When omitted, capability-gated SPA routes auto-use `true`
 *   (legacy behaviour). Pass `false` explicitly after successful `loginUser` so a session bug surfaces
 *   as a hard failure instead of an early "ready" on `/login`. Use `true` only for unauthenticated
 *   or redirect-to-login–positive scenarios.
 */

// ─── Route-smoke navigation helper ───────────────────────────────────────────
// Eliminates the 10-line boilerplate pattern repeated in every route-smoke test.

interface NavigateOrSkipOptions {
  /** CSS selector for expected page content (NOT .error-display — that's a failure). */
  contentSelector?: string;
  /** waitForAppMainReady timeout in ms (default 60000). */
  timeout?: number;
  /** Intercept the list API call for dual verification. Returns the response promise. */
  apiUrlPattern?: string;
}

interface NavigateOrSkipResult {
  /** false when the test was skipped (login redirect, 403, backend timeout). */
  ok: boolean;
  /** API response promise if apiUrlPattern was provided. Resolves to null if the API call
   *  was not captured (e.g. login redirect fired before the API call, or pattern didn't match). */
  apiResponse?: Promise<{ status: () => number; url: () => string } | null>;
}

/**
 * Navigate to a route using gotoWithRetry + waitForAppMainReady, with standard
 * skip-on-auth-failure handling. Replaces the 10-line boilerplate in every route test.
 *
 * Returns `{ ok: true }` when the page is ready for assertions.
 * Returns `{ ok: false }` and calls `test.skip()` when:
 *   - Redirected to /login (auth expired)
 *   - Redirected to /403 (role-gated, when allow403 is true)
 *
 * Does NOT accept .error-display as a ready state — callers must handle errors explicitly.
 */
export async function navigateOrSkip(
  page: Page,
  route: string,
  options: NavigateOrSkipOptions = {}
): Promise<NavigateOrSkipResult> {
  const { contentSelector, timeout = 60000, apiUrlPattern } = options;

  // Optionally intercept the API call BEFORE navigation for dual verification.
  // The .catch() prevents Playwright's "Test ended" error when the promise outlives
  // the test (e.g. login redirect fires before the API call, or the pattern doesn't match).
  let apiResponse: Promise<{ status: () => number; url: () => string } | null> | undefined;
  if (apiUrlPattern) {
    apiResponse = page.waitForResponse(
      (r) => r.url().includes(apiUrlPattern) && r.request().method() === 'GET',
      { timeout: timeout + 5000 }
    ).catch(() => null) as Promise<{ status: () => number; url: () => string } | null>;
  }

  // Dynamic import to avoid circular — gotoWithRetry is in auth.ts
  const { gotoWithRetry } = await import('./auth');
  await gotoWithRetry(page, route);

  try {
    await waitForAppMainReady(page, {
      timeout,
      acceptRedirectToLogin: true,
      contentSelector,
    });
  } catch (_err) {
    if (page.url().includes('/login')) {
      test.skip(true, `Redirected to login navigating to ${route} — auth may have expired`);
      return { ok: false };
    }
    throw _err;
  }

  if (page.url().includes('/login')) {
    test.skip(true, `Redirected to login after loading ${route} — auth may have expired`);
    return { ok: false };
  }

  return { ok: true, apiResponse };
}

export async function loginAndNavigateToRoute(
  page: Page,
  user: TestUser,
  route: string,
  options: { timeout?: number; contentSelector?: string; acceptRedirectToLogin?: boolean } = {}
): Promise<void> {
  const postLoginWait = 1000; // Brief settle after login; app-sidebar wait handles the real readiness check

  const doLogin = async (): Promise<void> => {
    await loginUser(page, user);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(postLoginWait);
  };

  const runNav = async (): Promise<void> => runNavToRoute(page, user, route, options);

  const maxRetries = 2; // initial + 2 retries; with subscription fix auth should work on first attempt
  let lastErr: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (attempt > 0) {
      await page.waitForTimeout(2000); // backoff between retries
      await doLogin();
    } else {
      await doLogin();
    }
    // Ensure app shell loaded before nav (avoids runNav when stuck on login)
    if (page.url().includes('/login')) {
      lastErr = new Error('loginAndNavigateToRoute: Redirected to login');
      if (attempt < maxRetries) continue;
      throw lastErr;
    }
    try {
      await page.locator('.app-sidebar').waitFor({ state: 'visible', timeout: 10000 });
    } catch (err) {
      lastErr =
        err instanceof Error
          ? new Error(
              `loginAndNavigateToRoute: App shell not visible after login. ${err.message}`
            )
          : err;
      if (attempt < maxRetries) continue;
      throw lastErr;
    }
    try {
      await runNav();
      return;
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      if (!msg.includes('Redirected to login') && !msg.includes('Still on login')) {
        throw err;
      }
    }
  }
  throw lastErr;
}

/** Capability-gated routes that often redirect to login; always accept redirect when option set. */
// /communities (Phase 27.2; was /social). social.ratings, social.reviews, social.comments on /assets/:id.
const CAPABILITY_GATED_ROUTES = ['/ai/search', '/ai/schema-matching', '/developer', '/baas', '/ml', '/communities', '/transformation'];

/** Run nav logic; throws on redirect-to-login. Used for retry. */
async function runNavToRoute(
  page: Page,
  user: TestUser,
  route: string,
  options: { timeout?: number; contentSelector?: string; acceptRedirectToLogin?: boolean }
): Promise<void> {
  const autoAcceptRedirect = CAPABILITY_GATED_ROUTES.some(
    (r) => route === r || route.startsWith(r + '/')
  );
  const acceptRedirectToLoginResolved =
    options.acceptRedirectToLogin !== undefined
      ? options.acceptRedirectToLogin
      : autoAcceptRedirect;
  const contentSelector = resolveRouteContentSelector(route, options.contentSelector);
  const waitOptions = {
    ...options,
    contentSelector,
    acceptRedirectToLogin: acceptRedirectToLoginResolved,
  };
  // /odps/upload: go to odps first, wait for list API, then click Create/Upload button
  if (route === '/odps/upload') {
    const odpsLabel = ROUTE_NAV_LABELS['/odps'];
    const odpsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: odpsLabel }).first();
    if ((await odpsLink.count()) > 0) {
      const odpsTimeout = options.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/odps', odpsTimeout);
      await odpsLink.click();
      await page.waitForLoadState('domcontentloaded');
      if (apiWait) await apiWait;
      await page.waitForTimeout(1500);
      const uploadBtn = page
        .locator(
          'button:has-text("Create ODPS Product"), button:has-text("Create ODPS"), button:has-text("Create Your First")'
        )
        .first();
      if ((await uploadBtn.count()) > 0) {
        await uploadBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /marketplace/listings/:id: go to marketplace, wait for list API, click listing card (client-side nav avoids goto auth race)
  const marketplaceListingMatch = route.match(/^\/marketplace\/listings\/([^/]+)$/);
  if (marketplaceListingMatch) {
    const listingId = marketplaceListingMatch[1];
    const marketplaceLabel = ROUTE_NAV_LABELS['/marketplace'];
    const marketplaceLink = page.locator('.app-sidebar .nav-link').filter({ hasText: marketplaceLabel }).first();
    if ((await marketplaceLink.count()) > 0) {
      const listTimeout = options.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/marketplace', listTimeout);
      await marketplaceLink.click();
      await page.waitForLoadState('domcontentloaded');
      if (apiWait) await apiWait;
      await page.waitForTimeout(1500);
      const listingCard = page.locator(`.listing-card[data-listing-id="${listingId}"]`).first();
      if ((await listingCard.count()) > 0) {
        await listingCard.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /marketplace/orders: go to marketplace first, then click My Orders
  if (route === '/marketplace/orders') {
    const marketplaceLabel = ROUTE_NAV_LABELS['/marketplace'];
    const marketplaceLink = page.locator('.app-sidebar .nav-link').filter({ hasText: marketplaceLabel }).first();
    if ((await marketplaceLink.count()) > 0) {
      await marketplaceLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);
      const ordersBtn = page.locator('button:has-text("My Orders")');
      if ((await ordersBtn.count()) > 0) {
        await ordersBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /marketplace/publish: go to marketplace first, wait for listings API, then click Publish Listing
  if (route === '/marketplace/publish') {
    const marketplaceLabel = ROUTE_NAV_LABELS['/marketplace'];
    const marketplaceLink = page.locator('.app-sidebar .nav-link').filter({ hasText: marketplaceLabel }).first();
    if ((await marketplaceLink.count()) > 0) {
      const listTimeout = options.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/marketplace', listTimeout);
      // Add explicit timeout — without it, click() retries indefinitely until
      // the test times out when the sidebar is blocked by an overlay or scroll issue.
      await marketplaceLink.click({ timeout: 30000 });
      await page.waitForLoadState('domcontentloaded');
      if (apiWait) await apiWait;
      await page.waitForTimeout(3000);
      // Publish Listing appears after marketplace page loads (listings API)
      const publishBtn = page
        .locator('button:has-text("Publish Listing")')
        .or(page.locator('.empty-state-action:has-text("Publish Listing")'));
      try {
        await publishBtn.first().waitFor({ state: 'visible', timeout: 25000 });
        await publishBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      } catch {
        // Publish button not found - fall through to goto
      }
    }
  }

  // /mesh/create: go to mesh first, then click Create Domain
  if (route === '/mesh/create') {
    const meshLabel = ROUTE_NAV_LABELS['/mesh'];
    const meshLink = page.locator('.app-sidebar .nav-link').filter({ hasText: meshLabel }).first();
    if ((await meshLink.count()) > 0) {
      await meshLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const createBtn = page
        .locator('button:has-text("Create Domain")')
        .or(page.locator('.empty-state-action:has-text("Create Domain")'));
      try {
        await createBtn.first().waitFor({ state: 'visible', timeout: 15000 });
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      } catch {
        // Create button not found - fall through to goto
      }
    }
  }

  // /virtualization/create: go to virtualization first, then click Create Dataset
  if (route === '/virtualization/create') {
    const virtLabel = ROUTE_NAV_LABELS['/virtualization'];
    const virtLink = page.locator('.app-sidebar .nav-link').filter({ hasText: virtLabel }).first();
    if ((await virtLink.count()) > 0) {
      await virtLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const createBtn = page
        .locator('button:has-text("Create Dataset")')
        .or(page.locator('.empty-state-action:has-text("Create Dataset")'))
        .or(page.locator('button:has-text("Create Virtual Dataset")'));
      try {
        await createBtn.first().waitFor({ state: 'visible', timeout: 15000 });
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      } catch {
        // Create button not found - fall through to goto
      }
    }
  }

  // /mesh/topology: go to mesh first, then look for topology link or use in-page nav
  if (route === '/mesh/topology') {
    const meshLabel = ROUTE_NAV_LABELS['/mesh'];
    const meshLink = page.locator('.app-sidebar .nav-link').filter({ hasText: meshLabel }).first();
    if ((await meshLink.count()) > 0) {
      await meshLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const topologyLink = page.locator('a[href*="/mesh/topology"], a[href="/mesh/topology"]').first();
      if ((await topologyLink.count()) > 0) {
        await topologyLink.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /assets/create: go to assets first, then click Create Asset
  if (route === '/assets/create') {
    const assetsLabel = ROUTE_NAV_LABELS['/assets'];
    const assetsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: assetsLabel }).first();
    if ((await assetsLink.count()) > 0) {
      await assetsLink.click({ timeout: 30000 });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);
      const createBtn = page
        .locator('button:has-text("Create Asset")')
        .or(page.locator('.empty-state-action:has-text("Create Asset")'));
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /odps/:id: go to ODPS list first, then click row (client-side nav avoids full-reload auth race)
  const odpsIdMatch = route.match(/^\/odps\/([^/]+)$/);
  if (odpsIdMatch && odpsIdMatch[1] !== 'upload') {
    const odpsContractId = odpsIdMatch[1];
    const odpsLabel = ROUTE_NAV_LABELS['/odps'];
    const odpsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: odpsLabel }).first();
    if ((await odpsLink.count()) > 0) {
      const timeout = options.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/odps', timeout);
      await odpsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (apiWait) await apiWait;
      const viewBtn = page.locator(`tr[data-odps-id="${odpsContractId}"] button`).first();
      if ((await viewBtn.count()) > 0) {
        await viewBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1500);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /assets/:id: go to assets, wait for list API, then click asset link (avoids goto auth race)
  const assetsIdMatch = route.match(/^\/assets\/([^/]+)$/);
  if (assetsIdMatch) {
    const assetId = assetsIdMatch[1];
    const assetsLabel = ROUTE_NAV_LABELS['/assets'];
    const assetsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: assetsLabel }).first();
    if ((await assetsLink.count()) > 0) {
      const listTimeout = options.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/assets', listTimeout);
      let doneViaSidebar = false;
      try {
        // Bounded wait: after long journeys an overlay or layout shift can block the sidebar
        // link indefinitely; fall through to injectTokens + goto below.
        await assetsLink.click({ timeout: 25000 });
        await page.waitForLoadState('domcontentloaded');
        if (apiWait) await apiWait;
        await page.waitForTimeout(1000);
        const assetRow = page.locator(`.asset-list-page tr[data-asset-id="${assetId}"]`).first();
        if ((await assetRow.count()) > 0) {
          await assetRow.click();
          await page.waitForLoadState('domcontentloaded');
          await page.waitForTimeout(1000);
          await waitForAppMainReady(page, waitOptions);
          doneViaSidebar = true;
        }
      } catch {
        if (apiWait) await apiWait.catch(() => null);
      }
      if (doneViaSidebar) return;
    }
  }

  // /datasets/create: go to datasets first, wait for list API, then click Create Dataset
  if (route === '/datasets/create') {
    const datasetsLabel = ROUTE_NAV_LABELS['/datasets'];
    const datasetsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: datasetsLabel }).first();
    if ((await datasetsLink.count()) > 0) {
      const timeout = options.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/datasets', timeout);
      await datasetsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (apiWait) await apiWait;
      await waitForLoadingComplete(page, { timeout: 20000 });
      const createBtn = page
        .locator('button:has-text("Create Dataset")')
        .or(page.locator('.empty-state-action:has-text("Create Dataset")'));
      try {
        await createBtn.first().waitFor({ state: 'visible', timeout: 15000 });
      } catch {
        /* Optional: Create button may not be visible (empty state, different UI); fall through to goto */
      }
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForURL(/\/datasets\/create/, { timeout: 15000 }).catch(() => null);
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /integrations/sync-jobs, /integrations/mappings: go to Integrations first, then click tab (client-side nav avoids full-reload auth race)
  if (route === '/integrations/sync-jobs' || route === '/integrations/mappings') {
    const intLabel = ROUTE_NAV_LABELS['/integrations/connections'];
    const intLink = page.locator('.app-sidebar .nav-link').filter({ hasText: intLabel }).first();
    if ((await intLink.count()) > 0) {
      await intLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1500); // IntegrationsLayout tabs to render
      const tabText = route === '/integrations/sync-jobs' ? 'Sync Jobs' : 'Mappings';
      const tabLink = page.locator(`.integrations-tab, a[href="${route}"]`).filter({ hasText: tabText }).first();
      if ((await tabLink.count()) > 0) {
        const timeout = options.timeout ?? 60000;
        const apiWait = startRouteDataApiWait(page, route, timeout); // Start before tab click so we catch the request
        await tabLink.click();
        await page.waitForLoadState('domcontentloaded');
        if (apiWait) await apiWait;
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  // /integrations/connections/create: go to Integrations first, then click Create Connection
  if (route === '/integrations/connections/create') {
    const intLabel = ROUTE_NAV_LABELS['/integrations/connections'];
    const intLink = page.locator('.app-sidebar .nav-link').filter({ hasText: intLabel }).first();
    if ((await intLink.count()) > 0) {
      await intLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const createBtn = page
        .locator('button:has-text("Create Connection")')
        .or(page.locator('.empty-state-action:has-text("Create Connection")'))
        .or(page.locator('button:has-text("Create Marketplace Connection")'));
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, waitOptions);
        return;
      }
    }
  }

  const label = ROUTE_NAV_LABELS[route];
  if (label) {
    const link = page.locator('.app-sidebar .nav-link').filter({ hasText: label }).first();
    if ((await link.count()) > 0) {
      // Sidebar groups (e.g. Admin) render as <details> closed by default.
      // The nav-link is in the DOM but not visible until <details> is open,
      // so a click on the hidden link spins until test timeout. Open the
      // enclosing <details> first if needed.
      if (!(await link.isVisible().catch(() => false))) {
        const parentDetails = link.locator('xpath=ancestor::details[1]');
        if ((await parentDetails.count()) > 0) {
          await parentDetails.evaluate((el: Element) => {
            (el as HTMLDetailsElement).open = true;
          }).catch(() => {});
        }
      }
      if (await link.isVisible().catch(() => false)) {
        const timeout = options.timeout ?? 30000;
        const apiWait = startRouteDataApiWait(page, route, timeout);
        await link.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        if (apiWait) await apiWait;
        await waitForAppMainReady(page, waitOptions);
        return;
      }
      // Link still hidden (filtered out by RBAC despite presence) — fall through to direct goto.
    }
  }

  // page.goto() triggers a full-page navigation that resets the JS context.
  // In-memory auth tokens are lost. Inject fresh tokens before goto.
  await injectTokensBeforeGotoForUser(page, user);
  const gotoTimeout = options.timeout ?? 30000;
  const gotoApiWait = startRouteDataApiWait(page, route, gotoTimeout);
  await gotoWithRetry(page, route);
  if (gotoApiWait) await gotoApiWait;
  try {
    await waitForAppMainReady(page, waitOptions);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes('Redirected to login') || msg.includes('Still on login')) {
      // Re-inject fresh tokens and retry navigation once
      await injectTokensBeforeGotoForUser(page, user);
      await gotoWithRetry(page, route);
      await waitForAppMainReady(page, waitOptions);
    } else {
      throw err;
    }
  }
}

/**
 * Normalize pathname for route comparison (strip trailing slash, query, hash).
 */
function normalizePath(pathOrUrl: string): string {
  try {
    const p = pathOrUrl.startsWith('/') ? pathOrUrl : new URL(pathOrUrl).pathname;
    return p.replace(/\/$/, '') || '/';
  } catch {
    return pathOrUrl.replace(/\/$/, '') || '/';
  }
}

/**
 * Navigate to a route from within the app (client-side nav only).
 * Use when already logged in and on a protected page. Avoids full-reload auth race.
 * Retries with re-login when redirected to login (auth may fail under parallel E2E load).
 * When already on the target route, skips navigation to avoid redundant remounts that can
 * trigger auth races (HomePage remount → many API calls → 401 under load).
 */
export async function navigateToRouteFromApp(
  page: Page,
  route: string,
  options: {
    timeout?: number;
    contentSelector?: string;
    acceptRedirectToLogin?: boolean;
    /** User for retries when redirected to login; defaults to getTestUser() */
    user?: TestUser;
  } = {}
): Promise<void> {
  const maxRetries = 4;
  let lastErr: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (attempt > 0) {
      const user = options.user ?? (await getTestUser());
      await loginUser(page, user);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
    }
    try {
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(500);
      const navOptions = { ...options };

      // If already on target route, skip navigation to avoid redundant remount (can trigger 401 under load)
      const currentPath = normalizePath(page.url());
      const targetPath = normalizePath(route);
      if (currentPath === targetPath && !page.url().includes('/login')) {
        await waitForAppMainReady(page, navOptions);
        return;
      }

      // Reuse same special-case logic as loginAndNavigateToRoute
  if (route === '/odps/upload') {
    const odpsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/odps'] }).first();
    if ((await odpsLink.count()) > 0) {
      await odpsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);
      const uploadBtn = page.locator('button:has-text("Create ODPS Product"), button:has-text("Create Your First")').first();
      if ((await uploadBtn.count()) > 0) {
        await uploadBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }
  const odpsIdMatch = route.match(/^\/odps\/([^/]+)$/);
  if (odpsIdMatch && odpsIdMatch[1] !== 'upload') {
    const odpsContractId = odpsIdMatch[1];
    const odpsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/odps'] }).first();
    if ((await odpsLink.count()) > 0) {
      const apiWait = startRouteDataApiWait(page, '/odps', navOptions.timeout ?? 60000);
      await odpsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (apiWait) await apiWait;
      const viewBtn = page.locator(`tr[data-odps-id="${odpsContractId}"] button`).first();
      if ((await viewBtn.count()) > 0) {
        await viewBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1500);
        await waitForAppMainReady(page, navOptions);
        return;
      }
    }
  }
  // /marketplace/listings/:id: client-side nav via listing card (avoids goto auth race)
  const marketplaceListingNavMatch = route.match(/^\/marketplace\/listings\/([^/]+)$/);
  if (marketplaceListingNavMatch) {
    const listingId = marketplaceListingNavMatch[1];
    const marketplaceLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/marketplace'] }).first();
    if ((await marketplaceLink.count()) > 0) {
      const listTimeout = navOptions.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/marketplace', listTimeout);
      await marketplaceLink.click();
      await page.waitForLoadState('domcontentloaded');
      if (apiWait) await apiWait;
      await page.waitForTimeout(1500);
      const listingCard = page.locator(`.listing-card[data-listing-id="${listingId}"]`).first();
      if ((await listingCard.count()) > 0) {
        await listingCard.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        await waitForAppMainReady(page, navOptions);
        return;
      }
    }
  }
  if (route === '/marketplace/publish') {
    const marketplaceLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/marketplace'] }).first();
    if ((await marketplaceLink.count()) > 0) {
      const listTimeout = navOptions.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/marketplace', listTimeout);
      await marketplaceLink.click();
      await page.waitForLoadState('domcontentloaded');
      if (apiWait) await apiWait;
      await page.waitForTimeout(3000);
      const publishBtn = page
        .locator('button:has-text("Publish Listing")')
        .or(page.locator('.empty-state-action:has-text("Publish Listing")'));
      try {
        await publishBtn.first().waitFor({ state: 'visible', timeout: 25000 });
        await publishBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1500);
      } catch {
        // Publish button not found - fall through to goto
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }
  if (route === '/mesh/create') {
    const meshLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/mesh'] }).first();
    if ((await meshLink.count()) > 0) {
      await meshLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const createBtn = page
        .locator('button:has-text("Create Domain")')
        .or(page.locator('.empty-state-action:has-text("Create Domain")'));
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }
  if (route === '/mesh/topology') {
    const meshLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/mesh'] }).first();
    if ((await meshLink.count()) > 0) {
      await meshLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const topologyLink = page.locator('a[href*="/mesh/topology"], a[href="/mesh/topology"]').first();
      if ((await topologyLink.count()) > 0) {
        await topologyLink.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }
  if (route === '/virtualization/create') {
    const virtLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/virtualization'] }).first();
    if ((await virtLink.count()) > 0) {
      await virtLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const createBtn = page
        .locator('button:has-text("Create Dataset")')
        .or(page.locator('.empty-state-action:has-text("Create Dataset")'))
        .or(page.locator('button:has-text("Create Virtual Dataset")'));
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }
  if (route === '/assets/create') {
    const assetsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/assets'] }).first();
    if ((await assetsLink.count()) > 0) {
      await assetsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);
      const createBtn = page.locator('button:has-text("Create Asset")').or(page.locator('.empty-state-action:has-text("Create Asset")'));
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }
  if (route === '/datasets/create') {
    const datasetsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/datasets'] }).first();
    if ((await datasetsLink.count()) > 0) {
      const timeout = navOptions.timeout ?? 60000;
      const apiWait = startRouteDataApiWait(page, '/datasets', timeout);
      await datasetsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (apiWait) await apiWait;
      await waitForLoadingComplete(page, { timeout: 20000 });
      const createBtn = page.locator('button:has-text("Create Dataset")').or(page.locator('.empty-state-action:has-text("Create Dataset")'));
      try {
        await createBtn.first().waitFor({ state: 'visible', timeout: 15000 });
      } catch {
        /* Optional: Create button may not be visible (empty state, different UI); fall through to goto */
      }
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForURL(/\/datasets\/create/, { timeout: 15000 }).catch(() => null);
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }

  // /integrations/sync-jobs, /integrations/mappings: go to Integrations first, then click tab (client-side nav)
  if (route === '/integrations/sync-jobs' || route === '/integrations/mappings') {
    const intLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/integrations/connections'] }).first();
    if ((await intLink.count()) > 0) {
      await intLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1500); // IntegrationsLayout tabs to render
      const tabText = route === '/integrations/sync-jobs' ? 'Sync Jobs' : 'Mappings';
      const tabLink = page.locator('.integrations-tab').filter({ hasText: tabText }).first();
      if ((await tabLink.count()) > 0) {
        const apiWait = startRouteDataApiWait(page, route, navOptions.timeout ?? 60000); // Start before tab click so we catch the request
        await tabLink.click();
        await page.waitForLoadState('domcontentloaded');
        if (apiWait) await apiWait;
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }

  // /integrations/connections/create: go to Integrations first, then click Create Connection
  if (route === '/integrations/connections/create') {
    const intLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/integrations/connections'] }).first();
    if ((await intLink.count()) > 0) {
      await intLink.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const createBtn = page
        .locator('button:has-text("Create Connection")')
        .or(page.locator('.empty-state-action:has-text("Create Connection")'))
        .or(page.locator('button:has-text("Create Marketplace Connection")'));
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }

  // /assets/:id - try sidebar+row click; fallback to direct goto when row not found (list may be loading/paginated)
  const assetsIdMatch = route.match(/^\/assets\/([^/]+)$/);
  if (assetsIdMatch) {
    const aid = assetsIdMatch[1];
    const assetsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: ROUTE_NAV_LABELS['/assets'] }).first();
    let doneViaSidebar = false;
    if ((await assetsLink.count()) > 0) {
      const listTimeout = navOptions.timeout ?? 30000;
      const apiWait = startRouteDataApiWait(page, '/assets', listTimeout);
      try {
        await assetsLink.click({ timeout: 25000 });
        await page.waitForLoadState('domcontentloaded');
        if (apiWait) await apiWait; // Wait for assets list API so row is available (avoids goto auth race)
        await page.waitForTimeout(1000);
        const assetRow = page.locator(`.asset-list-page tr[data-asset-id="${aid}"]`).first();
        if ((await assetRow.count()) > 0) {
          await assetRow.click();
          await page.waitForLoadState('domcontentloaded');
          await page.waitForTimeout(1000);
          await waitForAppMainReady(page, navOptions);
          doneViaSidebar = true;
        }
      } catch {
        if (apiWait) await apiWait.catch(() => null);
      }
    }
    if (doneViaSidebar) return;
    // Row not found or sidebar nav failed — direct goto is faster and more reliable
    const fallbackTimeout = navOptions.timeout ?? 30000;
    const apiWait = startRouteDataApiWait(page, route, fallbackTimeout);
    // Inject fresh auth tokens before page.goto — full-page navigation resets JS context
    await injectTokensBeforeGotoForUser(page, options.user);
    await page.goto(route, { waitUntil: 'domcontentloaded' });
    if (apiWait) await apiWait;
    await waitForAppMainReady(page, navOptions);
    return;
  }

  const label = ROUTE_NAV_LABELS[route];
  if (label) {
    const link = page.locator('.app-sidebar .nav-link').filter({ hasText: label }).first();
    if ((await link.count()) > 0) {
      const timeout = navOptions.timeout ?? 30000;
      const apiWait = startRouteDataApiWait(page, route, timeout);
      await link.click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);
      if (apiWait) await apiWait;
      await waitForAppMainReady(page, navOptions);
      return;
    }
  }

  // Fallback: direct navigation — inject auth tokens first
  const fallbackTimeout = navOptions.timeout ?? 30000;
  const fallbackApiWait = startRouteDataApiWait(page, route, fallbackTimeout);
  await injectTokensBeforeGotoForUser(page, options.user);
  await page.goto(route, { waitUntil: 'domcontentloaded' });
  if (fallbackApiWait) await fallbackApiWait;
  await waitForAppMainReady(page, navOptions);
  return;
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      if (!msg.includes('Redirected to login') && !msg.includes('Still on login')) {
        throw err;
      }
    }
  }
  throw lastErr;
}

/**
 * Wait for loading to complete.
 * Uses a short default timeout (5s) for the spinner; pass longer timeout for slow APIs (e.g. asset/dataset detail).
 */
export async function waitForLoadingComplete(
  page: Page,
  options: {
    timeout?: number;
    loadingSelector?: string;
  } = {}
): Promise<void> {
  const { timeout = 5000, loadingSelector = '.loading-spinner-container, .loading-spinner, .loading, [data-loading="true"]' } =
    options;

  try {
    await page.waitForSelector(loadingSelector, { state: 'hidden', timeout });
  } catch {
    // Loading spinner might not exist or may be stuck; continue
  }

  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1000);
}

/**
 * Assert API error response
 */
export async function assertApiError(
  page: Page,
  urlPattern: string | RegExp,
  expectedStatus: number,
  expectedMessage?: string | RegExp
): Promise<void> {
  const response = await waitForApiResponse(page, urlPattern, {
    status: expectedStatus,
  });

  if (expectedMessage) {
    // Intentional fallback: response body may be non-JSON when parsing fails
    const body = await response.json().catch(() => ({}));
    const message = body.message || body.error || JSON.stringify(body);

    if (typeof expectedMessage === 'string') {
      expect(message).toContain(expectedMessage);
    } else {
      expect(message).toMatch(expectedMessage);
    }
  }
}

/**
 * Assert element contains text (with retry)
 */
export async function assertContainsText(
  page: Page,
  selector: string,
  text: string | RegExp,
  options: {
    timeout?: number;
    exact?: boolean;
  } = {}
): Promise<void> {
  const { timeout = 10000, exact = false } = options;

  await waitForElement(page, selector, { timeout, state: 'visible' });

  const element = page.locator(selector);

  if (exact) {
    if (typeof text === 'string') {
      await expect(element).toHaveText(text, { timeout });
    } else {
      await expect(element).toHaveText(text, { timeout });
    }
  } else {
    if (typeof text === 'string') {
      await expect(element).toContainText(text, { timeout });
    } else {
      await expect(element).toContainText(text, { timeout });
    }
  }
}

/**
 * Assert element is visible (with retry)
 */
export async function assertVisible(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
  } = {}
): Promise<void> {
  const { timeout = 10000 } = options;

  await waitForElement(page, selector, { timeout, state: 'visible' });
  await expect(page.locator(selector)).toBeVisible({ timeout });
}

/**
 * Assert element is not visible
 */
export async function assertNotVisible(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
  } = {}
): Promise<void> {
  const { timeout = 5000 } = options;

  try {
    await expect(page.locator(selector)).toBeHidden({ timeout });
  } catch {
    // Element might not exist, which is fine
    const count = await page.locator(selector).count();
    if (count > 0) {
      throw new Error(`Element ${selector} is visible but should be hidden`);
    }
  }
}

/**
 * Take screenshot for debugging
 */
export async function takeDebugScreenshot(page: Page, name: string): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `debug-${name}-${timestamp}.png`;
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`Debug screenshot saved: ${filename}`);
}

/**
 * Wait for API call to complete (by monitoring network requests)
 */
export async function waitForApiCall(
  page: Page,
  method: string,
  urlPattern: string | RegExp,
  options: {
    timeout?: number;
    status?: number;
  } = {}
): Promise<Response> {
  const { timeout = 30000, status } = options;

  return await page.waitForResponse(
    (resp) => {
      const methodMatch = resp.request().method() === method.toUpperCase();
      const urlMatch =
        typeof urlPattern === 'string'
          ? resp.url().includes(urlPattern)
          : urlPattern.test(resp.url());

      if (!methodMatch || !urlMatch) return false;

      if (status !== undefined) {
        return resp.status() === status;
      }

      return resp.status() < 500;
    },
    { timeout }
  );
}

/**
 * Clean up test data (helper for test teardown)
 */
export async function cleanupTestData(
  page: Page,
  resourceType: string,
  resourceIds: string[]
): Promise<void> {
  const API_BASE_URL = process.env.E2E_API_BASE_URL || process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

  for (const id of resourceIds) {
    try {
      const token = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!token) {
        console.warn(`No access token found, skipping cleanup for ${resourceType} ${id}`);
        continue;
      }

      const response = await fetch(`${API_BASE_URL}/${resourceType}/${id}/`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok || response.status === 404) {
        console.log(`Cleaned up ${resourceType} ${id}`);
      } else {
        console.warn(`Failed to cleanup ${resourceType} ${id}: ${response.status}`);
      }
    } catch (error) {
      console.warn(`Error cleaning up ${resourceType} ${id}:`, error);
    }
  }
}

/**
 * Dual verification: assert successful load (backend + frontend).
 * Prevents false positives where API returns 2xx but frontend shows error.
 *
 * For success tests: API must return 2xx AND frontend must show success content
 * (no .error-display, no error message). Use as first verification after navigation.
 *
 * @param options.apiResponsePromise - Promise from page.waitForResponse() started BEFORE
 *   navigation. Caller must create this before goto so we capture the initial load response.
 *   Example: const p = page.waitForResponse(r => r.url().includes('contracts'));
 *            await page.goto('/contracts'); ... await assertSuccessfulLoad(page, { apiResponsePromise: p, ... });
 * @param options.successContentSelector - CSS selector(s) for expected success content.
 *   Comma-separated for multiple alternatives (e.g. '.contract-list-page, .empty-state').
 *   Empty state is valid success when API returned 2xx with empty data.
 * @param options.rejectErrorDisplay - When true (default), fails if .error-display is visible.
 *   Set false only for tests that expect mixed success/error states.
 */
export async function assertSuccessfulLoad(
  page: Page,
  options: {
    apiResponsePromise?: Promise<{ status: () => number; url: () => string }>;
    successContentSelector: string;
    timeout?: number;
    rejectErrorDisplay?: boolean;
  }
): Promise<void> {
  const {
    apiResponsePromise,
    successContentSelector,
    timeout = 30000,
    rejectErrorDisplay = true,
  } = options;

  // 1. Backend: assert API returned 2xx (caller must pass promise started before navigation)
  if (apiResponsePromise) {
    const response = await apiResponsePromise;
    const status = response.status();
    if (status < 200 || status >= 300) {
      throw new Error(
        `assertSuccessfulLoad: API returned ${status}, expected 2xx. ` +
          `Backend failed; frontend success cannot be assumed. URL: ${response.url()}`
      );
    }
  }

  // 2. Frontend: no error display (unless explicitly allowed)
  if (rejectErrorDisplay) {
    await page.waitForTimeout(1500); // Allow error UI to render if API failed
    const errorCount =
      (await page.locator('.error-display').count()) +
      (await page.locator('.error-display-title').count());
    const errorText = await page
      .locator('.error-display, .error-display-title, [role="alert"]')
      .filter({ hasText: /failed|error|404|500|forbidden|not found/i })
      .count();
    if (errorCount > 0 || errorText > 0) {
      const snippet = await page
        .locator('.error-display, .error-display-title')
        .first()
        .textContent()
        .catch(() => '');
      throw new Error(
        `assertSuccessfulLoad: Frontend shows error state (error-display or error text). ` +
          `Backend may have succeeded but UI indicates failure. Content: ${snippet?.slice(0, 100) ?? 'N/A'}`
      );
    }
  }

  // 3. Frontend: wait for expected success content (API returned 2xx; allow React to re-render)
  const combinedSelector = successContentSelector
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .join(', ');
  try {
    await page.locator(combinedSelector).first().waitFor({ state: 'visible', timeout });
  } catch {
    throw new Error(
      `assertSuccessfulLoad: No success content visible within ${timeout}ms. Expected one of: ${successContentSelector}. ` +
        `URL: ${page.url()}`
    );
  }
}

/**
 * Test dimension: Happy path helper
 * Verifies that all steps complete successfully
 */
export async function verifyHappyPath(
  page: Page,
  steps: Array<{
    name: string;
    action: () => Promise<void>;
    verify?: () => Promise<void>;
  }>
): Promise<void> {
  for (const step of steps) {
    try {
      console.log(`Executing step: ${step.name}`);
      await step.action();

      if (step.verify) {
        await step.verify();
      }

      console.log(`✅ Step completed: ${step.name}`);
    } catch (error) {
      console.error(`❌ Step failed: ${step.name}`, error);
      throw new Error(`Happy path step failed: ${step.name} - ${error}`);
    }
  }
}

/**
 * Test dimension: Failure scenario helper
 * Verifies error handling. When expectedError.status is set, intercepts API calls
 * matching urlPattern and asserts response.status() === expectedError.status
 * (see TEST_ASSERTION_CONVENTIONS: assert status when known).
 */
export async function verifyFailureScenario(
  page: Page,
  action: () => Promise<void>,
  expectedError: {
    /** When set with urlPattern, intercepts matching API and asserts response.status() === status */
    status?: number;
    /** API URL pattern (string or RegExp) to intercept when asserting status. Required when status is set. */
    urlPattern?: string | RegExp;
    message?: string | RegExp;
    selector?: string;
  }
): Promise<void> {
  const timeout = 15000;
  let actionError: unknown;

  const urlMatch = (url: string): boolean => {
    const pattern = expectedError.urlPattern;
    if (!pattern) return false;
    return typeof pattern === 'string' ? url.includes(pattern) : pattern.test(url);
  };

  // When status and urlPattern are set, wait for the API response (matching url + status) triggered by action()
  // We wait for response matching both urlPattern and expected status to avoid capturing a prior 200 and asserting on the wrong response.
  const responsePromise =
    expectedError.status != null && expectedError.urlPattern
      ? page
          .waitForResponse(
            (resp) => urlMatch(resp.url()) && resp.status() === expectedError.status!,
            { timeout }
          )
          .catch((e: unknown) => {
            const msg =
              e instanceof Error ? e.message : String(e);
            throw new Error(
              `verifyFailureScenario: No API response matching urlPattern with status ${expectedError.status} within ${timeout}ms. ${msg}`
            );
          })
      : null;

  try {
    await action();
  } catch (error) {
    actionError = error;
  }

  // Assert API response status when expectedError.status and urlPattern are provided
  if (expectedError.status != null && expectedError.urlPattern && responsePromise) {
    const response = await responsePromise;
    expect(
      response.status(),
      `API ${expectedError.urlPattern.toString()} should return ${expectedError.status}`
    ).toBe(expectedError.status);
  }

  // Verify error message on page when provided
  if (expectedError.message) {
    const messageSelector =
      expectedError.selector ?? '.app-main, .error-display, [role="alert"], body';
    await assertContainsText(page, messageSelector, expectedError.message);
  }

  // If action succeeded and we expected an error but did not assert it (no status+urlPattern), fail
  const assertedApiStatus =
    expectedError.status != null && expectedError.urlPattern && responsePromise !== null;
  if (
    actionError === undefined &&
    (expectedError.status != null || expectedError.message) &&
    !assertedApiStatus
  ) {
    throw new Error('Expected error but action succeeded');
  }
}

/**
 * Wait for the asset dropdown (select#asset_id) to have at least one asset option.
 * Polls until options appear or timeout. Use after createAssetViaApi + navigate to publish page.
 * Returns true if assets found; false if timeout (caller may skip).
 */
export async function waitForAssetDropdownOptions(
  page: Page,
  options: { timeout?: number; pollInterval?: number } = {}
): Promise<boolean> {
  const { timeout = 15000, pollInterval = 500 } = options;
  const assetSelect = page.locator('select#asset_id');
  await assetSelect.waitFor({ state: 'visible', timeout: 10000 });
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const opts = await assetSelect.locator('option').allTextContents();
    const hasAssets = opts.some((t) => t && t !== 'Select an asset...');
    if (hasAssets) return true;
    await page.waitForTimeout(pollInterval);
  }
  return false;
}

/**
 * Assert that navigating to a detail page with a non-existent ID shows a 404-style error.
 *
 * Valid outcomes:
 *   1. `.error-display` is visible AND `.error-display-message` contains "not found" text  ← PRIMARY
 *   2. Redirected to `/login` (user not authenticated)
 *   3. Redirected to `/403` or forbidden page (user lacks permission)
 *
 * Invalid outcomes (will throw — these were previously accepted as false positives):
 *   ❌ `noDetailContent` — ALWAYS true for nil UUID (detail never renders on 404), making the
 *      original assertion trivially true regardless of what the page shows. REMOVED.
 *   ❌ `stillLoading` — a stuck spinner means the API never responded; NOT a 404 boundary. REMOVED.
 *   ❌ `hasEmptyState` — empty state means the resource type works but has no data; NOT a 404. REMOVED.
 *   ❌ Generic `.error-display` without "not found" text — network errors and 500s must NOT pass. REMOVED.
 *
 * @param detailContentSelector  CSS selector(s) for the expected success content
 *   (e.g. '.asset-detail-page'). Included in the initial waitForSelector ONLY as a timing aid
 *   to let the page settle — it is NOT used as a fallback passing condition.
 * @param waitAfterLoad  Extra ms after the page settles, to allow error UI to finish rendering.
 * @param selectorTimeout  Timeout (ms) for the initial waitForSelector to reach any terminal state.
 * @param apiUrlPattern  Optional substring of the API URL for the nil UUID resource
 *   (e.g. '/assets/00000000-0000-0000-0000-000000000000'). When provided, the helper intercepts
 *   the matching response and asserts its HTTP status is 404. Non-404 responses (500, network
 *   error with no response) cause an explicit failure so infrastructure problems do not pass.
 */
export async function assertNonExistentIdShowsError(
  page: Page,
  options: {
    detailContentSelector?: string;
    waitAfterLoad?: number;
    selectorTimeout?: number;
    apiUrlPattern?: string;
  } = {}
): Promise<void> {
  const { detailContentSelector, waitAfterLoad = 5000, selectorTimeout = 30000, apiUrlPattern } = options;

  // If the caller provided the API URL pattern, intercept responses so we can verify
  // the HTTP status at the network layer — not just by looking at DOM text.
  let apiResponseStatus: number | null = null;
  if (apiUrlPattern) {
    page.on('response', (resp) => {
      if (resp.url().includes(apiUrlPattern)) {
        apiResponseStatus = resp.status();
      }
    });
  }

  // Wait for the page to reach a terminal state: error display, login redirect, or detail content.
  // The detail content selector is included only to avoid a blank-page timeout situation —
  // if the page somehow rendered the content we do NOT accept it as passing (see below).
  const waitSelector =
    '.error-display, .error-display-title, #email, [data-testid="forbidden-page"]' +
    (detailContentSelector ? `, ${detailContentSelector}` : '');

  await page.waitForSelector(waitSelector, { timeout: selectorTimeout }).catch(() => {
    throw new Error(
      `assertNonExistentIdShowsError: page did not reach a terminal state within ${selectorTimeout}ms.\n` +
        `Expected .error-display, a login redirect, or detail content.\n` +
        `URL: ${page.url()}\n` +
        `Selector waited for: ${waitSelector}`
    );
  });

  // Allow the error UI to finish rendering (e.g. async error message population).
  await page.waitForTimeout(waitAfterLoad);

  const url = page.url();
  const onLogin = url.includes('/login');
  const on403 = url.includes('/403');
  const onForbidden = (await page.locator('[data-testid="forbidden-page"]').count()) > 0;

  // Login and 403/forbidden redirects are acceptable outcomes for role-gated access.
  if (onLogin || on403 || onForbidden) return;

  // ── Check what the page actually rendered ────────────────────────────────

  const hasErrorDisplay =
    (await page.locator('.error-display').count()) > 0 ||
    (await page.locator('.error-display-title').count()) > 0;

  // Scope to .error-display-message (the <p> under the title) — NOT the full page.
  // "failed to load" intentionally omitted: it appears in the hardcoded <h3> title for
  // EVERY error type (404, 500, network down), making it useless as a discriminator.
  // Only the message element contains text that is specific to 404 responses.
  // 403 is also accepted: the backend returns 403 (not 404) for non-existent resources
  // within tenant isolation to prevent UUID enumeration attacks.
  const hasNotFoundText =
    (await page
      .locator('.error-display-message')
      .filter({
        hasText: /not found|could not be found|does not exist|404|403|forbidden|No .* matches the given query|Request failed with status (?:404|403)/i,
      })
      .count()) > 0;

  // ── Specific diagnostic messages for each failure mode ────────────────────

  if (!hasErrorDisplay) {
    // Check what IS on the page to give an actionable error
    const hasStillLoading =
      (await page.locator('.loading-spinner, .loading-spinner-container').count()) > 0;
    const hasEmptyState = (await page.locator('.empty-state').count()) > 0;
    const hasDetailContent = detailContentSelector
      ? (await page.locator(detailContentSelector).count()) > 0
      : false;

    if (hasDetailContent) {
      throw new Error(
        `assertNonExistentIdShowsError: the detail page rendered SUCCESSFULLY for a nil UUID.\n` +
          `This means the backend returned data for a non-existent resource — a data integrity bug.\n` +
          `URL: ${url}\n` +
          `Detail selector matched: ${detailContentSelector}`
      );
    }
    if (hasStillLoading) {
      throw new Error(
        `assertNonExistentIdShowsError: page is still loading (spinner visible) after ${waitAfterLoad}ms.\n` +
          `The API never responded or is hanging. A stuck spinner is NOT a passing 404 test.\n` +
          `URL: ${url}`
      );
    }
    if (hasEmptyState) {
      throw new Error(
        `assertNonExistentIdShowsError: page shows empty state for nil UUID.\n` +
          `Empty state means the resource type works but has no data — NOT a 404 error boundary.\n` +
          `URL: ${url}`
      );
    }
    throw new Error(
      `assertNonExistentIdShowsError: no .error-display visible for nil UUID.\n` +
        `Expected a "not found" error to be shown.\n` +
        `URL: ${url}`
    );
  }

  // Error display IS shown — verify it is a "not found" type, not a network/500 error.
  // A network error or 500 server error would also show .error-display, but those indicate
  // infrastructure problems, not a correctly handled 404. They must NOT make this test pass.
  if (!hasNotFoundText) {
    const errorText = await page
      .locator('.error-display, .error-display-title')
      .first()
      .textContent()
      .catch(() => '');
    throw new Error(
      `assertNonExistentIdShowsError: .error-display is visible but the error text does NOT indicate "not found".\n` +
        `Actual error: "${errorText?.slice(0, 300) ?? 'N/A'}"\n` +
        `This may be a network error, 500 server error, or auth failure — NOT a valid 404 boundary.\n` +
        `URL: ${url}`
    );
  }

  // Network-layer verification: if the caller provided an apiUrlPattern and we captured
  // a response, assert it was actually a 404. Non-404 statuses (500, 503, etc.) mean the
  // test passed only because of UI text — not because the API correctly returned "not found".
  if (apiUrlPattern && apiResponseStatus !== null && apiResponseStatus !== 404) {
    throw new Error(
      `assertNonExistentIdShowsError: API returned HTTP ${apiResponseStatus} (expected 404) for nil UUID.\n` +
        `Status ${apiResponseStatus} indicates ${apiResponseStatus >= 500 ? 'a server error' : 'an unexpected response'}, ` +
        `not a correctly handled 404 boundary.\n` +
        `URL: ${url}`
    );
  }

  // ✅ Both conditions met: error display is shown AND it contains "not found" text.
}

/**
 * Ensure asset has prerequisites for activation (ACTIVE contract with valid validation/normalization).
 * Creates contract via API, validates, attaches to asset, sets contract ACTIVE.
 * Uses page context (localStorage token) so caller must be logged in.
 * Returns { success: true } or { success: false, error: string }.
 * No mocks; real backend only.
 */
export async function ensureAssetActivationPrerequisites(
  page: Page,
  assetId: string
): Promise<{ success: boolean; error?: string }> {
  const result = await page.evaluate(
    async (aid: string) => {
      const token = localStorage.getItem('access_token');
      if (!token) return { success: false, error: 'No access token' };
      const base = `${window.location.origin}/api/v1`;

      /** Matches Asset.can_activate() rules using public GET endpoints (no optimistic shortcuts). */
      async function verifyActivationReadyForE2e(): Promise<boolean> {
        const ass = await fetch(`${base}/assets/${aid}/`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
        });
        if (!ass.ok) return false;
        const a = (await ass.json()) as {
          dataset_id?: string | null;
          dq_status?: string;
          compliance_status?: string;
        };
        const list = await fetch(`${base}/contracts/?asset_id=${aid}&status=ACTIVE`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
        });
        if (!list.ok) return false;
        const lj = (await list.json()) as {
          results?: Array<{ validation_status?: string; normalization_status?: string }>;
        };
        const validActive = (lj.results ?? []).some(
          (c) =>
            ['VALID', 'WARNING_ONLY'].includes(String(c.validation_status ?? '')) &&
            ['NORMALIZED_OK', 'NORMALIZED_WITH_WARNINGS'].includes(String(c.normalization_status ?? ''))
        );
        if (!validActive) return false;
        if (a.dataset_id) {
          if (!['PASS', 'WARN'].includes(String(a.dq_status ?? ''))) return false;
          if (!['PASS', 'WARN'].includes(String(a.compliance_status ?? ''))) return false;
        }
        return true;
      }

      // Try E2E-only backend helper first (when RATE_LIMIT_E2E_RELAX or ENVIRONMENT=test).
      // This endpoint creates a contract with VALID/NORMALIZED_OK status directly in the DB,
      // bypassing the async validation/normalization pipeline — much faster and more reliable
      // under parallel E2E load than the full flow.
      // Retry up to 3 times: under heavy load the first request may timeout or 503.
      for (let helperAttempt = 0; helperAttempt < 3; helperAttempt++) {
        try {
          const helperRes = await fetch(`${base}/assets/${aid}/ensure-e2e-activation-prerequisites/`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            cache: 'no-store',
          });
          if (helperRes.ok) {
            if (await verifyActivationReadyForE2e()) return { success: true };
            // POST succeeded but reads are not yet consistent (cache/replica/propagation). Back off
            // before retry: without delay, three tight POSTs on a non-idempotent backend create
            // redundant ACTIVE contracts and load the tenant.
            if (helperAttempt < 2) {
              await new Promise((r) => setTimeout(r, 2000 * (helperAttempt + 1)));
            }
            continue;
          }
          if (helperRes.status === 404) break; // Helper not available; fall through to full flow
          if (helperRes.status >= 500 && helperAttempt < 2) {
            await new Promise((r) => setTimeout(r, 2000 * (helperAttempt + 1)));
            continue; // Retry on 5xx
          }
          const err = await helperRes.text();
          return { success: false, error: `E2E helper: ${helperRes.status} ${err}` };
        } catch {
          // Network error (timeout, ECONNRESET) — retry
          if (helperAttempt < 2) {
            await new Promise((r) => setTimeout(r, 2000 * (helperAttempt + 1)));
            continue;
          }
          // Last attempt failed — fall through to full flow
          break;
        }
      }

      // Full flow: create contract, validate, attach, set ACTIVE
      // Use valid ODCS 3.0.0 format (matches examples/contracts/odcs_test_3_0_0.json)
      const contractJson = {
        apiVersion: 'odcs.io/v3.0.0',
        kind: 'DataContract',
        id: `e2e-activate-${Date.now()}`,
        name: 'E2E Activation Contract',
        version: '1.0.0',
        schema: {
          fields: [
            { name: 'id', type: 'string' },
            { name: 'name', type: 'string' },
          ],
        },
      };

      const contractRes = await fetch(`${base}/contracts/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        cache: 'no-store',
        body: JSON.stringify({
          asset_id: aid,
          original_spec_type: 'ODCS',
          original_spec_version: '3.0.0',
          original_format: 'JSON',
          original_raw: JSON.stringify(contractJson),
        }),
      });
      if (!contractRes.ok) {
        const err = await contractRes.text();
        return { success: false, error: `Contract create: ${contractRes.status} ${err}` };
      }
      const contract = await contractRes.json();
      const contractId = contract.id;
      let contractVersion = contract.version || 1;

      const validateRes = await fetch(`${base}/contracts/${contractId}/validate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        cache: 'no-store',
        body: JSON.stringify({ async: false }),
      });
      if (!validateRes.ok) {
        const err = await validateRes.text();
        return { success: false, error: `Contract validate: ${validateRes.status} ${err}` };
      }

      const pollInterval = 2000;
      const maxAttempts = 60; // 60 × 2s = 120s: backend contract validation can be slow under parallel load
      let contractData: { validation_status?: string; normalization_status?: string; version?: number } | null = null;
      for (let i = 0; i < maxAttempts; i++) {
        await new Promise((r) => setTimeout(r, pollInterval));
        const check = await fetch(`${base}/contracts/${contractId}/`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
        });
        if (check.ok) {
          contractData = await check.json();
          const vs = contractData.validation_status;
          const ns = contractData.normalization_status;
          if (
            (vs === 'VALID' || vs === 'WARNING_ONLY') &&
            (ns === 'NORMALIZED_OK' || ns === 'NORMALIZED_WITH_WARNINGS')
          ) {
            contractVersion = contractData.version ?? contractVersion;
            break;
          }
        }
      }
      if (
        !contractData ||
        !['VALID', 'WARNING_ONLY'].includes(contractData.validation_status || '') ||
        !['NORMALIZED_OK', 'NORMALIZED_WITH_WARNINGS'].includes(contractData.normalization_status || '')
      ) {
        return {
          success: false,
          error: `Contract validation/normalization failed: validation=${contractData?.validation_status ?? '?'}, normalization=${contractData?.normalization_status ?? '?'}`,
        };
      }

      // Contract was created with asset_id, so already attached; skip attach step
      const patchRes = await fetch(`${base}/contracts/${contractId}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        cache: 'no-store',
        body: JSON.stringify({ status: 'ACTIVE', version: contractVersion }),
      });
      if (!patchRes.ok) {
        const err = await patchRes.text();
        return { success: false, error: `Contract ACTIVE: ${patchRes.status} ${err}` };
      }
      // Allow backend to propagate ACTIVE status before asset activation (avoid race condition)
      await new Promise((r) => setTimeout(r, 3000));
      if (await verifyActivationReadyForE2e()) return { success: true };
      // Dataset assets need dq/compliance PASS|WARN; public PATCH cannot set those — hit E2E helper.
      for (let postAttempt = 0; postAttempt < 3; postAttempt++) {
        try {
          const h = await fetch(`${base}/assets/${aid}/ensure-e2e-activation-prerequisites/`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            cache: 'no-store',
          });
          if (h.ok && (await verifyActivationReadyForE2e())) return { success: true };
        } catch {
          /* retry */
        }
        await new Promise((r) => setTimeout(r, 2000 * (postAttempt + 1)));
      }
      return {
        success: false,
        error:
          'Contract flow finished but activation preconditions still fail (dq/compliance or ACTIVE contract visibility).',
      };
    },
    assetId
  );
  return result as { success: boolean; error?: string };
}

/**
 * Test dimension: Edge case helper
 * Verifies boundary conditions
 */
// ─── Route-smoke assertion helpers ───────────────────────────────────────────
// Used by batch-2 route specs to eliminate false positives.

/**
 * Assert that a list page loaded successfully.
 *
 * - Throws if `.error-display` is visible — a broken/errored page is NEVER a success.
 * - Waits for the specific list-page component or `.empty-state` to become visible.
 *   An empty state is a valid success: the backend returned 2xx with zero results.
 *
 * NOTE: Do NOT include `.error-display` in `listPageSelector`. If you need to allow
 * error states, use `assertSuccessfulLoad` with `rejectErrorDisplay: false` instead.
 *
 * @param listPageSelector Comma-separated CSS selectors for the list page + empty state.
 *   Example: '.order-list-page, .empty-state'
 */
export async function assertListPageLoads(
  page: Page,
  listPageSelector: string,
  options: { timeout?: number } = {}
): Promise<void> {
  const { timeout = 30000 } = options;

  // Fail immediately if we're on /login — this means auth is broken, not that
  // the page hasn't loaded yet. Success tests must NOT accept login redirect as
  // a pass; that hides real auth/backend failures. (This was the root cause of
  // 60%+ of tests giving false confidence when the backend was unreachable.)
  if (page.url().includes('/login')) {
    throw new Error(
      `assertListPageLoads: redirected to /login before content loaded.\n` +
        `Expected content on: ${listPageSelector}\n` +
        `This means authentication is broken — storageState tokens may be expired, ` +
        `the auth service may be down, or the refresh flow failed.\n` +
        `This is a REAL FAILURE, not a "skip" condition.`
    );
  }

  // Race-based detection: wait for EITHER the expected success content OR an error to appear.
  // This eliminates the previous 800ms static window where a slow-responding API error
  // would be missed by an early check, then produce a misleading "element not found" timeout.
  //
  // By racing both selectors together, the waitFor resolves as soon as the page reaches
  // any terminal state — whether that's a valid list/empty-state or an error display.
  const errorSelector = '.error-display, .error-display-title';
  const combinedSelector = `${listPageSelector}, ${errorSelector}`;

  try {
    await page
      .locator(combinedSelector)
      .first()
      .waitFor({ state: 'visible', timeout });
  } catch {
    // Check for login redirect first — auth may have failed during the wait
    if (page.url().includes('/login')) {
      throw new Error(
        `assertListPageLoads: redirected to /login while waiting for content.\n` +
          `Expected content on: ${listPageSelector}\n` +
          `Auth token likely expired during page load or API returned 401.`
      );
    }

    // Neither success content nor error appeared within the timeout.
    // Check if the page is actively loading (skeleton/spinner visible) — if so, the
    // backend is slow but the app is working. Wait for the loading state to resolve.
    const hasLoading =
      (await page.locator('.loading-spinner, .loading-spinner-container, [data-testid="skeleton-row"], .skeleton').count()) > 0;
    if (hasLoading) {
      // Page is actively loading — wait for content or error to appear after loading
      try {
        await page
          .locator(combinedSelector)
          .first()
          .waitFor({ state: 'visible', timeout: 30000 });
      } catch {
        // Loading persisted beyond extended wait — backend truly unresponsive
        throw new Error(
          `assertListPageLoads: page still loading after ${timeout + 30000}ms (backend slow under parallel E2E load).\n` +
            `Expected one of: ${listPageSelector}\n` +
            `URL: ${page.url()}`
        );
      }
    } else {
      throw new Error(
        `assertListPageLoads: neither success content nor an error display appeared within ${timeout}ms.\n` +
          `Expected one of: ${listPageSelector}\n` +
          `URL: ${page.url()}\n` +
          `Possible cause: API is unresponsive, route is missing, or CSS class name changed.`
      );
    }
  }

  // Check which branch won the race: error state or success state?
  const errorCount =
    (await page.locator('.error-display').count()) +
    (await page.locator('.error-display-title').count());
  if (errorCount > 0) {
    const errText = (await page
      .locator('.error-display, .error-display-title')
      .first()
      .textContent()
      .catch(() => '')) ?? '';
    // Backend timeout under parallel E2E load is transient — the app correctly shows the
    // error, but the backend couldn't respond in time. Distinguish from real errors so
    // callers can decide whether to skip or fail.
    const isTimeoutError = /timeout.*exceeded|timed out|ETIMEDOUT|ECONNRESET|socket hang up/i.test(errText);
    const errorType = isTimeoutError ? 'BACKEND_TIMEOUT' : 'ERROR_STATE';
    throw new Error(
      `assertListPageLoads: ${errorType}: page shows error state.\n` +
        `Error content: "${errText.slice(0, 300)}"\n` +
        `URL: ${page.url()}`
    );
  }

  // Success branch: the list/empty-state is already visible (we just raced it).
  // Final explicit assertion keeps Playwright's built-in retry and produces a clean pass.
  await expect(page.locator(listPageSelector).first()).toBeVisible({ timeout: 3000 });
}

/**
 * Assert that a capability-gated or role-gated page loaded correctly.
 *
 * Valid outcomes:
 *   1. The specific feature page rendered (capability enabled, user has role)
 *   2. `.unavailable-page` rendered (capability disabled)
 *   3. URL redirected to `/403` or `/login`
 *
 * Invalid outcomes (will throw):
 *   - `.error-display` is visible — this is a service crash, not a gating outcome
 *   - `.app-main` alone — the generic app shell tells us nothing about page content
 *
 * @param featurePageSelector Comma-separated selectors for the feature page component.
 *   Do NOT include `.app-main` or `.error-display`.
 *   Example: '.developer-page, .unavailable-page'
 */
export async function assertCapabilityGatedPageLoads(
  page: Page,
  featurePageSelector: string,
  options: { timeout?: number } = {}
): Promise<void> {
  const { timeout = 30000 } = options;
  const url = page.url();

  // Redirect to login or 403 is always an acceptable outcome for gated/role-gated routes
  if (url.includes('/login') || url.includes('/403')) return;

  // Race-based detection: wait for EITHER the expected feature content OR an error to appear.
  // Eliminates the previous static 800ms window that missed slow-responding API errors and
  // produced misleading "element not found" timeouts instead of actionable error messages.
  //
  // The featurePageSelector passed by callers must include '.unavailable-page' so that
  // capability-disabled redirects (CapabilityRoute → /unavailable) are also captured.
  const errorSelector = '.error-display, .error-display-title';
  const combinedSelector = `${featurePageSelector}, ${errorSelector}`;

  await page
    .locator(combinedSelector)
    .first()
    .waitFor({ state: 'visible', timeout })
    .catch(() => {
      throw new Error(
        `assertCapabilityGatedPageLoads: no expected content appeared within ${timeout}ms.\n` +
          `Expected one of: ${featurePageSelector}\n` +
          `URL: ${page.url()}\n` +
          `Possible cause: capability is loading indefinitely, route is missing, or CSS class name changed.`
      );
    });

  // Check which branch won the race: crash/error state or valid feature/gating state?
  const errorCount =
    (await page.locator('.error-display').count()) +
    (await page.locator('.error-display-title').count());
  if (errorCount > 0) {
    const errText = await page
      .locator('.error-display, .error-display-title')
      .first()
      .textContent()
      .catch(() => '');
    throw new Error(
      `assertCapabilityGatedPageLoads: page shows error state (service crash, NOT a gating outcome).\n` +
        `Error content: "${errText?.slice(0, 300) ?? 'N/A'}"\n` +
        `URL: ${page.url()}`
    );
  }

  // Success branch: the feature page or unavailable page is already visible.
  // Final explicit assertion for a clean pass record in the Playwright report.
  await expect(page.locator(featurePageSelector).first()).toBeVisible({ timeout: 3000 });
}

export async function verifyEdgeCase(
  page: Page,
  testCase: {
    name: string;
    setup: () => Promise<void>;
    action: () => Promise<void>;
    verify: () => Promise<void>;
  }
): Promise<void> {
  console.log(`Testing edge case: ${testCase.name}`);

  await testCase.setup();
  await testCase.action();
  await testCase.verify();

  console.log(`✅ Edge case passed: ${testCase.name}`);
}

// ─── UI Workflow Interaction Helpers ────────────────────────────────────────
// These helpers perform real UI interactions (clicks, form fills, navigation)
// and return observable outcomes. They do NOT mock or stub any backend calls.

/**
 * Click the tenant switcher button in the header and select a tenant by name.
 * Sets up a request listener to capture the X-Tenant-Id header sent by subsequent requests.
 * Returns the new tenant name displayed in the header after the switch.
 *
 * Throws if the tenant switcher button is not visible or the requested tenant is not in the list.
 */
export async function switchTenantViaUI(
  page: Page,
  tenantName: string
): Promise<{ newTenantName: string; switchRequestUrl: string }> {
  // Find the tenant switcher button in the header
  const switcherButton = page.locator(
    '[data-testid="tenant-switcher"], .tenant-button, button[aria-label="Switch tenant"]'
  );
  await expect(switcherButton.first()).toBeVisible({ timeout: 10000 });

  // Open the dropdown
  await switcherButton.first().click();

  // Wait for the dropdown to open
  const dropdown = page.locator(
    '.tenant-dropdown, [data-testid="tenant-dropdown"], [role="menu"]'
  );
  await expect(dropdown.first()).toBeVisible({ timeout: 8000 });

  // Wait for tenant list to load.
  // Timeout raised from 15s to 30s: the dropdown fetches /auth/me/tenants/ to populate
  // the list. Under parallel E2E load, this API call can take 15-25s to respond.
  await page.waitForFunction(
    (name) => {
      const menu = document.querySelector('.tenant-dropdown, [data-testid="tenant-dropdown"], [role="menu"]');
      return menu && menu.textContent?.includes(name);
    },
    tenantName,
    { timeout: 30000 }
  );

  // Click the target tenant option
  const tenantOption = dropdown.first().locator(
    `button:has-text("${tenantName}"), [role="menuitem"]:has-text("${tenantName}")`
  );
  await expect(tenantOption.first()).toBeVisible({ timeout: 5000 });

  // Capture the switch-tenant request URL
  let switchRequestUrl = '';
  const switchResponse = page.waitForResponse(
    (resp) => resp.url().includes('/auth/switch-tenant/') && resp.request().method() === 'POST',
    { timeout: 15000 }
  );
  await tenantOption.first().click();

  const switchResp = await switchResponse;
  switchRequestUrl = switchResp.url();
  expect(switchResp.status()).toBe(200);

  // Wait for header to reflect the new tenant name
  await page.waitForFunction(
    (name) => {
      const switcher = document.querySelector(
        '[data-testid="tenant-switcher"], .tenant-button, .tenant-static'
      );
      return switcher && switcher.textContent?.includes(name);
    },
    tenantName,
    { timeout: 10000 }
  ).catch(() => null); // non-fatal — some UIs refresh the page instead

  // Read the displayed tenant name
  const displayedName =
    (await page.locator('[data-testid="tenant-switcher"], .tenant-button, .tenant-static')
      .first()
      .textContent()
      .catch(() => tenantName)) ?? tenantName;

  return { newTenantName: displayedName.trim(), switchRequestUrl };
}

/**
 * Trigger a DQ run via the modal on the /dq list page.
 *
 * The DQ create form lives in a modal dialog opened by the "Create DQ run" button on the
 * DQRunListPage — there is no /dq/runs/new route. This helper:
 *   1. Navigates to /dq and waits for the list page to fully render
 *   2. Clicks the modal trigger button (.dq-create-run-btn or [data-testid="btn-create-dq-run"])
 *   3. Selects the asset via the AssetPicker (data-testid="dq-create-asset-picker")
 *      NOTE: Only asset is set; dataset picker is intentionally skipped because:
 *        a) DQ run only requires at least one of asset/dataset/file
 *        b) After asset selection the dataset picker's form group shows a loading spinner
 *           and a "Browse assets" overlay link that intercepts clicks until settled
 *   4. Submits and intercepts POST /dq/runs/
 *   5. Returns { runId, httpStatus }
 *
 * Throws on any failure — callers decide whether to surface or annotate.
 * Does NOT wait for the run to complete — use waitForDQRunViaApi for that.
 */
export async function triggerDQRunViaUI(
  page: Page,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  assetId: string,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  options?: { datasetId?: string }
): Promise<{ runId: string; httpStatus: number }> {
  await page.goto('/dq');
  await page.waitForLoadState('domcontentloaded');

  if (page.url().includes('/login')) {
    throw new Error('triggerDQRunViaUI: redirected to login — user is not authenticated');
  }
  if (page.url().includes('/403')) {
    throw new Error('triggerDQRunViaUI: user does not have permission to access DQ runs');
  }

  // Wait for the list page to settle (loading spinner → list or empty state)
  await page.waitForSelector(
    '.dq-run-list-page, .loading-spinner-container',
    { timeout: 30000 }
  );
  await page.waitForSelector(
    '.dq-run-list-page',
    { timeout: 30000 }
  );

  // Click the "Create DQ run" modal trigger button (stable data-testid preferred)
  const triggerBtn = page
    .locator('[data-testid="btn-create-dq-run"], button.dq-create-run-btn')
    .first();
  await triggerBtn.waitFor({ state: 'visible', timeout: 10000 });
  await triggerBtn.click();

  // Wait for modal dialog
  const modal = page.locator('[role="dialog"][aria-labelledby="dq-create-modal-title"]');
  await modal.waitFor({ state: 'visible', timeout: 10000 });

  // Select asset via AssetPicker (data-testid="dq-create-asset-picker")
  const assetPickerContainer = page.locator('[data-testid="dq-create-asset-picker"]');
  await assetPickerContainer.waitFor({ state: 'visible', timeout: 10000 });

  // Wait for any spinner inside the asset picker form group to disappear before clicking
  await page
    .locator('[data-testid="dq-create-asset-picker"] .loading-spinner')
    .first()
    .waitFor({ state: 'detached', timeout: 10000 })
    .catch(() => null);

  // AssetPicker searches by asset NAME (not UUID). Open with an empty query so the API
  // returns assets ordered by -created_at. The most recently created asset appears first.
  // We click the FIRST available option — any asset satisfies the DQ run requirement.
  // A newly created asset may not be visible immediately; retry up to 3 times.
  const assetPickerInput = assetPickerContainer.locator('input').first();
  if ((await assetPickerInput.count()) > 0) {
    let pickerOptionSelected = false;
    for (let pickerAttempt = 0; pickerAttempt < 3; pickerAttempt++) {
      if (pickerAttempt > 0) {
        await page.waitForTimeout(3000);
      }
      // Open with empty query → loads most-recent assets by -created_at
      await assetPickerInput.click();
      await assetPickerInput.fill('');
      const listbox = page.locator('[role="listbox"]').first();
      await listbox.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      const firstOption = page.locator('[role="listbox"] [role="option"]').first();
      if ((await firstOption.count()) > 0) {
        await firstOption.click();
        pickerOptionSelected = true;
        break;
      }
      // Retry with name-prefix search on subsequent attempts
      await assetPickerInput.fill('E2E Publish');
      await page.waitForTimeout(600);
      const namedOption = page.locator('[role="listbox"] [role="option"]').first();
      if ((await namedOption.count()) > 0) {
        await namedOption.click();
        pickerOptionSelected = true;
        break;
      }
    }
    if (!pickerOptionSelected) {
      // Last-resort fallback: search by 'e2e' prefix
      await assetPickerInput.fill('e2e');
      await page.waitForTimeout(1000);
      const anyOption = page.locator('[role="listbox"] [role="option"]').first();
      if ((await anyOption.count()) > 0) {
        await anyOption.click();
      }
    }
    // After selecting, wait for the AssetPicker to settle before submitting
    await page.waitForTimeout(300);
  }

  // NOTE: Dataset picker is intentionally not filled here.
  // The asset picker's "Browse assets" link overlaps the dataset picker form group and
  // intercepts pointer events after asset selection until the next render cycle.
  // A DQ run only requires at least one of asset/dataset/file, so asset alone is sufficient.
  // The `options?.datasetId` parameter is kept for API compatibility but not used in UI flow.

  const responsePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes('/dq/runs/') && resp.request().method() === 'POST',
    { timeout: 30000 }
  );

  // Submit the modal form; wait for button to be enabled (form validation passes)
  const submitBtn = modal.locator('button[type="submit"]').first();
  await submitBtn.waitFor({ state: 'visible', timeout: 5000 });
  // Verify the button is enabled (form requires at least one of asset/dataset/file)
  const isDisabled = await submitBtn.isDisabled().catch(() => false);
  if (isDisabled) {
    throw new Error(
      'triggerDQRunViaUI: submit button is disabled — asset selection may have failed. ' +
      'Ensure the asset picker listbox appeared and an option was clicked.'
    );
  }
  await submitBtn.click();

  const resp = await responsePromise;
  const respStatus = resp.status();
  const bodyText = await resp.text().catch(() => '');
  if (respStatus >= 400) {
    throw new Error(
      `triggerDQRunViaUI: POST /dq/runs/ returned ${respStatus}: ${bodyText.slice(0, 300)}`
    );
  }
  let data: { id?: string; run_id?: string } = {};
  try {
    data = JSON.parse(bodyText) as { id?: string; run_id?: string };
  } catch {
    throw new Error(
      `triggerDQRunViaUI: POST /dq/runs/ returned ${respStatus} but body is not JSON: ${bodyText.slice(0, 200)}`
    );
  }
  const runId = data.id || data.run_id;
  if (!runId) {
    throw new Error(`triggerDQRunViaUI: POST /dq/runs/ response missing run id. Body: ${bodyText.slice(0, 200)}`);
  }
  return { runId, httpStatus: respStatus };
}

/**
 * Trigger a compliance scan via the modal on the /compliance list page.
 *
 * The compliance create form is a modal dialog opened by the "Create compliance run" button
 * on the ComplianceRunListPage — there is no /compliance/runs/new route. This helper:
 *   1. Navigates to /compliance
 *   2. Clicks the modal trigger button (.compliance-create-run-btn)
 *   3. Selects the asset via AssetPicker (data-testid="compliance-create-asset-picker")
 *   4. Optionally selects a dataset/file
 *   5. Submits and intercepts POST /compliance/runs/
 *   6. Returns { runId, httpStatus }
 *
 * Throws on any failure — callers decide whether to surface or annotate.
 */
export async function triggerComplianceScanViaUI(
  page: Page,
  assetId: string,
  options?: { datasetId?: string; fileId?: string; assetName?: string }
): Promise<{ runId: string; httpStatus: number }> {
  await page.goto('/compliance');
  await page.waitForLoadState('domcontentloaded');

  if (page.url().includes('/login')) {
    throw new Error('triggerComplianceScanViaUI: redirected to login — user is not authenticated');
  }
  if (page.url().includes('/403')) {
    throw new Error('triggerComplianceScanViaUI: user does not have permission to access compliance runs');
  }

  // Wait for list page to fully load (not just the loading spinner)
  await page.waitForSelector(
    '.compliance-run-list-page, .empty-state',
    { timeout: 45000 }
  );

  // Click the modal trigger (stable data-testid preferred)
  const triggerBtn = page
    .locator('[data-testid="btn-create-compliance-run"], button.compliance-create-run-btn')
    .first();
  await triggerBtn.waitFor({ state: 'visible', timeout: 10000 });
  await triggerBtn.click();

  // Wait for modal dialog
  const modal = page.locator('[role="dialog"][aria-labelledby="compliance-create-modal-title"]');
  await modal.waitFor({ state: 'visible', timeout: 10000 });

  // Select asset via AssetPicker (data-testid="compliance-create-asset-picker").
  // Same pattern as DQ: wait for listbox to appear, click first option.
  // Dataset picker intentionally skipped (same overlay interception issue as DQ modal).
  const assetPickerContainer = page.locator('[data-testid="compliance-create-asset-picker"]');
  await assetPickerContainer.waitFor({ state: 'visible', timeout: 10000 });

  // AssetPicker searches by asset NAME (not UUID).
  // If assetName is provided, search by that exact name so we select the right asset.
  // Otherwise fall back to empty-query (first by -created_at).
  const assetPickerInput = assetPickerContainer.locator('input').first();
  if ((await assetPickerInput.count()) > 0) {
    let pickerOptionSelected = false;
    const searchTerms = options?.assetName
      ? [options.assetName, options.assetName.split(' ')[0], 'e2e']
      : ['', 'E2E Publish', 'e2e'];

    for (let pickerAttempt = 0; pickerAttempt < searchTerms.length; pickerAttempt++) {
      if (pickerAttempt > 0) {
        await page.waitForTimeout(2000);
      }
      await assetPickerInput.click();
      await assetPickerInput.fill(searchTerms[pickerAttempt]);

      // Wait for the asset picker's own listbox (scoped to the picker
      // container) to appear with at least one option. The previous
      // implementation used a page-wide `[role="listbox"]` selector
      // which could match other dropdowns, and swallowed timeouts via
      // .catch(() => null) — both hid real failures.
      const scopedListbox = assetPickerContainer.locator('[role="listbox"]');
      const scopedOption = scopedListbox.locator('[role="option"]');

      try {
        await scopedOption.first().waitFor({ state: 'visible', timeout: 10000 });
      } catch {
        // No options appeared for this search term — try the next one
        continue;
      }

      // If searching by name, prefer an exact match; otherwise take first
      let targetOption = scopedOption.first();
      if (options?.assetName && pickerAttempt === 0) {
        const exactMatch = scopedListbox
          .locator(`[role="option"]:has-text("${options.assetName}")`)
          .first();
        if ((await exactMatch.count()) > 0) targetOption = exactMatch;
      }

      await targetOption.click();
      pickerOptionSelected = true;
      break;
    }
    if (!pickerOptionSelected) {
      throw new Error('triggerComplianceScanViaUI: could not select any asset in the picker');
    }
    await page.waitForTimeout(300);
  }

  // NOTE: Dataset picker skipped — same overlay interception issue as DQ modal.
  // Compliance run only requires at least one of asset/dataset/file.

  const responsePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes('/compliance/runs/') && resp.request().method() === 'POST',
    { timeout: 15000 }
  );

  const submitBtn = modal.locator('button[type="submit"]').first();
  await submitBtn.waitFor({ state: 'visible', timeout: 5000 });
  const isDisabled = await submitBtn.isDisabled().catch(() => false);
  if (isDisabled) {
    throw new Error(
      'triggerComplianceScanViaUI: submit button is disabled — asset selection may have failed.'
    );
  }
  await submitBtn.click();

  const resp = await responsePromise;
  const compRespStatus = resp.status();
  const compBodyText = await resp.text().catch(() => '');
  if (compRespStatus >= 400) {
    throw new Error(
      `triggerComplianceScanViaUI: POST /compliance/runs/ returned ${compRespStatus}: ${compBodyText.slice(0, 300)}`
    );
  }
  let compData: { id?: string; run_id?: string } = {};
  try {
    compData = JSON.parse(compBodyText) as { id?: string; run_id?: string };
  } catch {
    throw new Error(
      `triggerComplianceScanViaUI: POST /compliance/runs/ returned ${compRespStatus} but body is not JSON: ${compBodyText.slice(0, 200)}`
    );
  }
  const runId = compData.id || compData.run_id;
  if (!runId) {
    throw new Error(`triggerComplianceScanViaUI: POST /compliance/runs/ response missing run id. Body: ${compBodyText.slice(0, 200)}`);
  }
  return { runId, httpStatus: compRespStatus };
}

/**
 * Navigate to the ODPS upload page, upload a JSON file at filePath, and submit.
 * Intercepts POST /contracts/ and returns { contractId }.
 * Throws if the HTTP response status is not 2xx.
 */
export async function uploadODPSContractViaUI(
  page: Page,
  filePath: string
): Promise<{ contractId: string }> {
  // Phase 219.7.4: /odps/upload, /contracts/odps-upload, /odps/new are dead routes.
  // The unified ContractCreatePage at /contracts/create handles both ODCS and ODPS
  // via auto-detection (detectSpecType). /odps/upload redirects to /contracts/create
  // (backward-compat route in routes.tsx), so try the canonical path first.
  const routes = ['/contracts/create', '/odps/upload'];

  for (const route of routes) {
    // Inject fresh auth tokens before page.goto — full-page navigation resets
    // the JS context and loses in-memory tokens, causing redirect to /login.
    await injectTokensBeforeGotoForUser(page);

    await page.goto(route, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    if (page.url().includes('/403') || page.url().includes('/login')) {
      throw new Error('uploadODPSContractViaUI: permission denied');
    }

    const fileInput = page.locator('input[type="file"]');
    if ((await fileInput.count()) === 0) continue;

    await fileInput.first().setInputFiles(filePath);

    // Wait for the file to be processed by ContractFileReader (reads content
    // asynchronously) and the submit button to become enabled. The previous
    // fixed 1s wait was insufficient — file read + spec detection can take
    // longer on staging with large payloads.
    const submitBtn = page.locator(
      'button:has-text("Create Contract"), button[type="submit"]:has-text("Create"), button:has-text("Upload"), button:has-text("Create ODPS"), button[type="submit"]:has-text("Submit"), button:has-text("Submit ODPS")'
    );
    if ((await submitBtn.count()) === 0) continue;

    // Wait for button to become enabled (file content processed, hasContent=true)
    try {
      await submitBtn.first().waitFor({ state: 'visible', timeout: 10000 });
      // Poll until the button is enabled (disabled attr removed after file is parsed)
      await expect(submitBtn.first()).toBeEnabled({ timeout: 15000 });
    } catch {
      // Button stayed disabled — file content wasn't detected; continue to next route
      continue;
    }

    // Phase 225.5 fix: ContractCreatePage runs a debounced validation
    // (1.5s after content change) via POST /contracts/validate-draft/.
    // If validate-draft returns {valid: false}, the submit button is
    // re-disabled (`validationBlocks = true`). The button-enable check
    // above passes BEFORE the debounce fires, then the button goes
    // disabled again — clicking a disabled button is a no-op.
    //
    // Root-cause fix: wait for the validation response to arrive AND
    // for the button to remain enabled after it settles. If validation
    // blocks the button, surface the validation errors rather than
    // failing with a vague "no creation POST" timeout.
    const validationSettled = page.waitForResponse(
      (r) => r.url().includes('/validate-draft') && r.request().method() === 'POST',
      { timeout: 10000 },
    ).catch(() => null);

    // Give debounce + network time to fire.
    const validationResp = await validationSettled;
    if (validationResp) {
      // Validation fired. Re-check button after a short settle window:
      // the React state update from the validation response takes one
      // more render cycle (~100-300 ms).
      await page.waitForTimeout(500);
    }

    // If the button re-disabled (validation blocked), extract the
    // error messages from the UI so the caller gets actionable output.
    const stillEnabled = await submitBtn.first().isEnabled();
    if (!stillEnabled) {
      // Read the validation panel for error details.
      const panelText = await page
        .locator('.validation-result, .contract-create-page__validation, [data-testid="validation-result"]')
        .textContent({ timeout: 3000 })
        .catch(() => '(no validation panel found)');
      throw new Error(
        `uploadODPSContractViaUI: submit button disabled after validation settled. ` +
        `The uploaded document failed pre-submit validation. ` +
        `Validation panel: ${(panelText || '').slice(0, 300)}`
      );
    }

    // Capture ALL POST responses to /contracts/ or /odps/ after clicking submit.
    // The form may fire a validation pre-flight POST (to /contracts/validate-draft/)
    // before the creation POST (to /contracts/ or /contracts/products/). We need
    // the creation response, not the validation one.
    const collectedResponses: Array<{ url: string; status: number; body: string }> = [];
    const responseHandler = async (resp: import('@playwright/test').Response) => {
      if (
        resp.request().method() === 'POST' &&
        (resp.url().includes('/contracts/') || resp.url().includes('/odps/'))
      ) {
        const body = await resp.text().catch(() => '');
        collectedResponses.push({ url: resp.url(), status: resp.status(), body });
      }
    };
    page.on('response', responseHandler);

    await submitBtn.first().click();

    // Wait for a creation response (one that contains an id or workflow_instance_id).
    // Poll collected responses for up to 30s.
    let creationResp: { url: string; status: number; body: string } | null = null;
    for (let poll = 0; poll < 60; poll++) {
      await page.waitForTimeout(500);
      for (const r of collectedResponses) {
        // Skip validation/normalization responses (no id, contain validate-draft in URL)
        if (/validate-draft|validate\/|normalize\//.test(r.url)) continue;
        creationResp = r;
        break;
      }
      if (creationResp) break;
    }
    page.off('response', responseHandler);

    if (!creationResp) {
      throw new Error(
        `uploadODPSContractViaUI: no creation POST response received within 30s. ` +
        `Collected ${collectedResponses.length} responses: ${collectedResponses.map(r => r.url).join(', ')}`
      );
    }

    if (creationResp.status < 200 || creationResp.status >= 300) {
      throw new Error(`uploadODPSContractViaUI: POST failed with ${creationResp.status}: ${creationResp.body}`);
    }

    let data: Record<string, unknown>;
    try { data = JSON.parse(creationResp.body); } catch { data = {}; }
    const typedData = data as {
      id?: string;
      odps_contract?: { id?: string };
      odcs_contract?: { id?: string };
      workflow_instance_id?: string;
      status?: string;
    };
    // The ODPS product creation endpoint returns {odps_contract: {id}, odcs_contract: {id}, workflow_instance_id}
    // for synchronous execution, or {workflow_instance_id, status: "RUNNING"} for async.
    let contractId = typedData.id || typedData.odps_contract?.id || typedData.odcs_contract?.id;

    // Async workflow: poll until completed, then extract contract id from result
    if (!contractId && typedData.workflow_instance_id) {
      const wfId = typedData.workflow_instance_id;
      const wfToken = await page.evaluate(() => localStorage.getItem('access_token'));
      for (let poll = 0; poll < 30; poll++) {
        await page.waitForTimeout(3000);
        try {
          const statusResp = await page.request.get(
            `/api/v1/contracts/products/workflows/${wfId}/status/`,
            { headers: wfToken ? { Authorization: `Bearer ${wfToken}` } : undefined }
          );
          if (statusResp.ok()) {
            const wfData = (await statusResp.json()) as Record<string, unknown>;
            const wfStatus = wfData.status as string | undefined;
            if (wfStatus === 'COMPLETED' || wfStatus === 'SUCCEEDED') {
              // The workflow status response puts odps_contract/odcs_contract at
              // the TOP level (not nested under 'result'). Extract contract id
              // from all possible locations.
              const odps = wfData.odps_contract as { id?: string } | undefined;
              const odcs = wfData.odcs_contract as { id?: string } | undefined;
              const result = wfData.result as { contract_id?: string; odps_contract?: { id?: string }; odcs_contract?: { id?: string } } | undefined;
              contractId = odps?.id || odcs?.id || result?.contract_id || result?.odps_contract?.id || result?.odcs_contract?.id || (wfData.contract_id as string | undefined);
              break;
            }
            if (wfStatus === 'FAILED') {
              throw new Error(`uploadODPSContractViaUI: workflow ${wfId} FAILED`);
            }
          }
        } catch (pollErr) {
          if (String(pollErr).includes('FAILED')) throw pollErr;
          // Transient error — retry
        }
      }
    }

    if (!contractId) throw new Error(`uploadODPSContractViaUI: response missing contract id. Body: ${creationResp.body.slice(0, 300)}`);
    return { contractId };
  }

  throw new Error('uploadODPSContractViaUI: could not find ODPS upload form at any known route');
}

/**
 * Navigate to an admin user edit page, change role checkboxes, and save.
 * Intercepts PATCH /admin/users/{userId}/ and returns { httpStatus, responseBody }.
 */
export async function changeUserRolesViaAdminUI(
  page: Page,
  userId: string,
  rolesToAdd: string[],
  rolesToRemove: string[]
): Promise<{ httpStatus: number; responseBody: Record<string, unknown> }> {
  await page.goto(`/admin/users/${userId}/edit`);
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1500);

  if (page.url().includes('/403') || page.url().includes('/login')) {
    throw new Error('changeUserRolesViaAdminUI: permission denied');
  }

  await page.waitForSelector('.user-edit-page, .user-edit-form, form', { timeout: 15000 });

  // Add roles — checkboxes are inside <label class="user-edit-role-checkbox"> with a role name span;
  // no value/id/name on the <input> itself, so we locate by label text.
  for (const role of rolesToAdd) {
    const checkbox = page
      .locator('.user-edit-role-checkbox')
      .filter({ hasText: new RegExp(role.replace('_', '[ _]'), 'i') })
      .locator('input[type="checkbox"]');
    const fallback = page.locator(
      `input[type="checkbox"][value="${role}"], input[type="checkbox"][name*="${role}"]`
    );
    const cb = (await checkbox.count()) > 0 ? checkbox : fallback;
    if ((await cb.count()) > 0 && !(await cb.first().isChecked())) {
      await cb.first().check();
    }
  }

  // Remove roles
  for (const role of rolesToRemove) {
    const checkbox = page
      .locator('.user-edit-role-checkbox')
      .filter({ hasText: new RegExp(role.replace('_', '[ _]'), 'i') })
      .locator('input[type="checkbox"]');
    const fallback = page.locator(
      `input[type="checkbox"][value="${role}"], input[type="checkbox"][name*="${role}"]`
    );
    const cb = (await checkbox.count()) > 0 ? checkbox : fallback;
    if ((await cb.count()) > 0 && (await cb.first().isChecked())) {
      await cb.first().uncheck();
    }
  }

  const responsePromise = page.waitForResponse(
    (resp) =>
      (resp.url().includes(`/admin/users/${userId}`) || resp.url().includes(`/users/${userId}`)) &&
      (resp.request().method() === 'PATCH' || resp.request().method() === 'PUT'),
    { timeout: 30000 }
  );

  const saveBtn = page.locator(
    'button[type="submit"]:has-text("Save"), button:has-text("Update"), button:has-text("Save changes")'
  );
  await expect(saveBtn.first()).toBeVisible({ timeout: 10000 });
  await saveBtn.first().click();

  const resp = await responsePromise;
  const responseBody = (await resp.json().catch(() => ({}))) as Record<string, unknown>;
  return { httpStatus: resp.status(), responseBody };
}

/**
 * Navigate to governance access requests page, find a pending request, and click Approve.
 * Intercepts the approval PATCH/POST and returns { requestId, httpStatus }.
 * Returns null (and does NOT throw) if no pending request is found.
 */
export async function approveAccessRequestViaUI(
  page: Page
): Promise<{ requestId: string; httpStatus: number } | null> {
  await page.goto('/governance/access-requests');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000);

  if (page.url().includes('/403') || page.url().includes('/login')) {
    return null; // Permission-gated — caller should decide whether to skip
  }

  await page.waitForSelector(
    '.governance-access-requests-page, .access-requests-list, .empty-state, .error-display',
    { timeout: 15000 }
  );

  // Find a pending request row
  const pendingRow = page.locator(
    'tr:has-text("PENDING"), tr:has-text("Pending"), [data-status="PENDING"]'
  ).first();
  if ((await pendingRow.count()) === 0) return null;

  // Extract the request ID from the row's data attribute or link
  const rowLink = pendingRow.locator('a[href*="/governance/access-requests/"]').first();
  let requestId = '';
  if ((await rowLink.count()) > 0) {
    const href = (await rowLink.getAttribute('href')) ?? '';
    requestId = href.split('/').filter(Boolean).pop() ?? '';
  }

  const approveBtn = pendingRow.locator(
    'button:has-text("Approve"), [data-action="approve"]'
  ).first();
  if ((await approveBtn.count()) === 0) return null;

  const responsePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes('/governance/access-requests/') &&
      (resp.request().method() === 'PATCH' || resp.request().method() === 'POST'),
    { timeout: 15000 }
  );

  await approveBtn.click();

  // Handle confirmation dialog
  const confirmDialog = page.locator('[role="dialog"], .confirm-dialog');
  if ((await confirmDialog.count()) > 0) {
    const confirmBtn = confirmDialog.first().locator(
      'button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Approve")'
    );
    if ((await confirmBtn.count()) > 0) await confirmBtn.first().click();
  }

  const resp = await responsePromise;
  return { requestId, httpStatus: resp.status() };
}
