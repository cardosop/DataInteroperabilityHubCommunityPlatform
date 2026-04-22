/**
 * Create Test User Setup
 * Creates a test user via API for E2E tests
 */

import * as fs from 'fs';
import * as path from 'path';

import { e2eTestHeaders } from '../fixtures/e2e-token';

/** Compare API base URLs ignoring trailing slashes. */
function normalizeApiBaseUrl(u: string): string {
  return u.replace(/\/+$/, '');
}

/**
 * When global-setup ran `ensure_e2e_subscription` successfully, it writes this marker.
 * Skips redundant per-test POST /test/ensure-e2e-subscription/ (same outcome, less API load
 * and fewer ECONNRESET warnings under parallel workers).
 */
function isSubscriptionPrimedForBaseUrl(baseUrl: string): boolean {
  try {
    const markerPath = path.join(process.cwd(), 'e2e', '.auth', 'subscription-primed.json');
    if (!fs.existsSync(markerPath)) return false;
    const raw = fs.readFileSync(markerPath, 'utf8');
    const data = JSON.parse(raw) as { apiBaseUrl?: string };
    if (typeof data.apiBaseUrl !== 'string') return false;
    return normalizeApiBaseUrl(data.apiBaseUrl) === normalizeApiBaseUrl(baseUrl);
  } catch {
    return false;
  }
}

// Node fetch needs absolute URL; VITE_API_BASE_URL is relative (/api/v1)
// Prefer 8001 when E2E_WEB_PORT set (test stack uses 8001)
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

// Remote API detection: when targeting a deployed environment (staging/production),
// docker exec and self-registration are unavailable. Users must be pre-seeded via
// kubectl exec or E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD must point to an existing user.
const _isRemoteApi = (() => {
  try {
    const h = new URL(API_BASE_URL).hostname;
    return h !== 'localhost' && h !== '127.0.0.1';
  } catch {
    return false;
  }
})();

export interface TestUser {
  email: string;
  password: string;
  name: string;
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

/** True when error is ECONNREFUSED (wrong port or backend not running). */
function isConnectionRefused(error: unknown): boolean {
  const cause = error && typeof error === 'object' && (error as { cause?: unknown }).cause;
  const msg = String((error as Error)?.message ?? '');
  const causeMsg = cause && typeof cause === 'object' ? String((cause as Error)?.message ?? '') : '';
  const code = cause && typeof cause === 'object' ? (cause as { code?: string }).code : undefined;
  return code === 'ECONNREFUSED' || /ECONNREFUSED/i.test(msg) || /ECONNREFUSED/i.test(causeMsg);
}

/** True when error is a transient connection/network failure (retryable) */
function isConnectionError(error: unknown): boolean {
  if (error instanceof TypeError && error.message === 'fetch failed') return true;
  const msg = String((error as Error)?.message ?? '');
  if (/ECONNREFUSED|ECONNRESET|socket hang up|other side closed|network|SocketError/i.test(msg))
    return true;
  const cause = error && typeof error === 'object' && (error as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'UND_ERR_SOCKET' || c.code === 'ECONNREFUSED' || c.code === 'ECONNRESET')
      return true;
    if (
      typeof c.message === 'string' &&
      /other side closed|socket hang up|network/i.test(c.message)
    )
      return true;
  }
  return false;
}

const FETCH_RETRIES = 6;
const RETRY_DELAYS_MS = [2000, 4000, 6000, 8000, 10000, 12000];

/** True when error is Postgres "too many clients" (transient under parallel E2E load) */
function isTooManyClientsError(error: unknown): boolean {
  const msg = String((error as Error)?.message ?? '');
  return /too many clients|too many connections/i.test(msg);
}

/** True when error is host resolution (API container temporarily cannot resolve postgres/postgres-test) */
function isHostResolutionRetryable(error: unknown): boolean {
  const msg = String((error as Error)?.message ?? '');
  return /cannot resolve host|translate host name|name resolution|getaddrinfo|ENOTFOUND|could not translate/i.test(msg);
}

function isRateLimitError(error: unknown): boolean {
  const msg = String((error as Error)?.message ?? '');
  return /rate.?limit|429|too many requests/i.test(msg);
}

function isTransientServerError(error: unknown): boolean {
  const msg = String((error as Error)?.message ?? '');
  return /deadlock|lock timeout|statement timeout|too many connections|500.*deadlock|REGISTRATION_FAILED|registration failed|SERVICE_UNAVAILABLE|INTERNAL_ERROR/i.test(msg);
}

/** Run fn with retries on transient connection errors, rate limits, and deadlocks */
async function withRetry<T>(fn: () => Promise<T>, label: string): Promise<T> {
  const maxAttempts = FETCH_RETRIES + 2; // Extra retries for host resolution (longer recovery)
  let lastError: unknown;
  for (let i = 0; i < maxAttempts; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const retryable =
        isConnectionError(error) ||
        isTooManyClientsError(error) ||
        isRateLimitError(error) ||
        isTransientServerError(error) ||
        (i < 4 && isHostResolutionRetryable(error));
      if (i < maxAttempts - 1 && retryable) {
        // Use longer delays for rate limits to let the limiter window expire
        const baseDelay = RETRY_DELAYS_MS[Math.min(i, RETRY_DELAYS_MS.length - 1)] ?? 8000;
        const delay = isRateLimitError(error) ? Math.max(baseDelay, 5000) : baseDelay;
        const reason = isTooManyClientsError(error)
          ? 'Postgres pool exhausted'
          : isHostResolutionRetryable(error)
            ? 'host resolution (API recovering)'
            : isRateLimitError(error)
              ? 'rate limited / account locked (429)'
              : 'connection error';
        console.log(
          `⚠️ ${label} failed (${reason}), retrying in ${delay}ms (attempt ${i + 1}/${maxAttempts})...`
        );
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw error;
    }
  }
  throw lastError;
}

/** Per-worker cache to avoid repeated API calls (ensureTestUser hits /auth/login/ on every call) */
let _cachedDefaultUser: TestUser | null = null;

/**
 * Create or get test user for E2E tests
 * Cached per worker to reduce API load and rate-limit pressure when many tests call getTestUser().
 * On ECONNREFUSED (wrong port), tries alternate port 8000 <-> 8001.
 */
export async function ensureTestUser(): Promise<TestUser> {
  if (_cachedDefaultUser) return _cachedDefaultUser;

  // Credentials from env vars (staging/CI) with fallback to local defaults.
  // E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD are set by deploy.yml e2e-staging job.
  const email = process.env.E2E_ADMIN_EMAIL || 'e2e_test@example.com';
  const password = process.env.E2E_ADMIN_PASSWORD || 'TestPass123'; // Must contain uppercase, lowercase, and number
  const name = 'E2E Test User';

  const runWithBase = async (baseUrl: string): Promise<TestUser> => {
    let loginResult = await withRetry(async () => {
      const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (loginResponse.ok) {
        console.log('✅ Test user exists and can login');
        return { email, password, name } as TestUser;
      }
      if (loginResponse.status === 429) {
        throw new Error('Rate limited (429); will retry');
      }
      return null;
    }, 'Test user login');

    if (!loginResult && _isRemoteApi) {
      // Remote API: docker exec is unavailable but self-registration IS.
      // The test user may have been wiped by a pod restart or DB migration.
      // Try to re-register before giving up (same pattern persona users use).
      const registered = await registerPersonaViaApi(
        { email, password, name },
        baseUrl
      );
      if (registered) {
        // Wait for DB to propagate, then retry login
        await new Promise((r) => setTimeout(r, 3000));
        loginResult = await withRetry(async () => {
          const resp = await fetch(`${baseUrl}/auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });
          if (resp.ok) {
            console.log('✅ Test user login OK after re-registration');
            return { email, password, name } as TestUser;
          }
          if (resp.status === 429) {
            throw new Error('Rate limited (429); will retry');
          }
          return null;
        }, 'Test user login (after re-register)');
      }
      if (!loginResult) {
        throw new Error(
          `Test user '${email}' login failed on remote API (${baseUrl}).\n` +
            'On deployed environments, test users must be pre-seeded. Run:\n' +
            '  kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles\n' +
            'Or set E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD to an existing user.'
        );
      }
    }

    if (!loginResult) {
      await runEnsureE2EUserRoles();
      await new Promise((r) => setTimeout(r, 2000));
      loginResult = await withRetry(async () => {
        const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (loginResponse.ok) return { email, password, name } as TestUser;
        return null;
      }, 'Test user login (retry after ensure)');
    }

    if (loginResult) {
      await ensureE2ESubscriptionForUser(loginResult, baseUrl);
      return loginResult;
    }

    const registered = await withRetry(async () => {
      console.log('Test user login failed, attempting to create user...');
      const registerResponse = await fetch(`${baseUrl}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      });

      if (registerResponse.ok) {
        console.log('✅ Test user created successfully');
        return { email, password, name };
      }
      // Intentional fallback: malformed JSON (e.g. HTML error page) -> empty object for error parsing
      const errorData = await registerResponse.json().catch(() => ({}));
      if ((registerResponse.status === 400 || registerResponse.status === 409) && isAlreadyRegisteredError(errorData)) {
        console.log('⚠️  Test user already registered, syncing password via ensure_e2e_user_roles');
        await runEnsureE2EUserRoles();
        await new Promise((r) => setTimeout(r, 2000));
        const retryLogin = await fetch(`${baseUrl}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (retryLogin.ok) {
          console.log('✅ Test user login OK after ensure_e2e_user_roles');
          return { email, password, name };
        }
        throw new Error(
          `Test user exists but login failed after ensure_e2e_user_roles. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
        );
      }
      const errMsg =
        typeof (errorData as { error?: { message?: string } })?.error?.message === 'string'
          ? (errorData as { error: { message: string } }).error.message
          : '';
      const isHostResolutionError =
        registerResponse.status === 500 &&
        /translate host name|name resolution|getaddrinfo|ENOTFOUND|could not translate/i.test(errMsg);
      if (isHostResolutionError) {
        throw new Error(
          `Backend at ${baseUrl.replace(/\/api\/v1\/?$/, '')} cannot resolve host "postgres". ` +
            'E2E requires the API to run inside Docker (api-service) so it can reach postgres. ' +
            'Start the stack: docker compose -f docker-compose.dev.yml up -d and ensure no process on the host is bound to port 8000.'
        );
      }
      // "too many clients" is transient (Postgres pool exhausted under parallel E2E); retry will be handled by withRetry
      throw new Error(
        `Registration failed: ${registerResponse.status} - ${JSON.stringify(errorData)}`
      );
    }, 'Test user register');
    await ensureE2ESubscriptionForUser(registered, baseUrl);
    return registered;
  };

  try {
    const user = await runWithBase(API_BASE_URL);
    _cachedDefaultUser = user;
    return user;
  } catch (err) {
    const alt = getAlternateApiBase(API_BASE_URL);
    if (alt && (isConnectionRefused(err) || isConnectionError(err))) {
      try {
        const user = await runWithBase(alt);
        _cachedDefaultUser = user;
        return user;
      } catch {
        // Fall through to rethrow original
      }
    }
    throw err;
  }
}

/** Must match hub `ensure_e2e_user_roles.PROFILE_ISOLATION_WORKER_COUNT` */
export const PROFILE_ISOLATION_WORKER_COUNT = 16;

const _cachedProfileIsolationUser = new Map<number, TestUser>();

/**
 * Dedicated E2E user per Playwright worker for tests that PATCH display_name.
 * Avoids cross-worker races on shared `e2e_test@` (parallel Success vs Edge profile tests).
 */
export async function ensureProfileIsolationUser(workerIndex: number): Promise<TestUser> {
  const idx = Math.min(
    Math.max(0, workerIndex),
    PROFILE_ISOLATION_WORKER_COUNT - 1
  );
  const cached = _cachedProfileIsolationUser.get(idx);
  if (cached) return cached;

  const emailTemplate = `e2e_profile_w${idx}@example.com`;
  const password = 'TestPass123';
  const name = `E2E Profile Worker ${idx}`;

  const runWithBase = async (baseUrl: string): Promise<TestUser> => {
    let loginResult = await withRetry(async () => {
      const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailTemplate, password }),
      });
      if (loginResponse.ok) {
        return { email: emailTemplate, password, name } as TestUser;
      }
      if (loginResponse.status === 429) {
        throw new Error('Rate limited (429); will retry');
      }
      return null;
    }, 'Profile isolation user login');

    if (!loginResult) {
      await runEnsureE2EUserRoles();
      await new Promise((r) => setTimeout(r, 2000));
      loginResult = await withRetry(async () => {
        const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: emailTemplate, password }),
        });
        if (loginResponse.ok) return { email: emailTemplate, password, name } as TestUser;
        return null;
      }, 'Profile isolation user login (retry after ensure)');
    }

    if (loginResult) {
      await ensureE2ESubscriptionForUser(loginResult, baseUrl);
      return loginResult;
    }
    throw new Error(
      `Profile isolation user ${emailTemplate} missing. ` +
        `Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
    );
  };

  try {
    const user = await runWithBase(API_BASE_URL);
    _cachedProfileIsolationUser.set(idx, user);
    return user;
  } catch (err) {
    const alt = getAlternateApiBase(API_BASE_URL);
    if (alt && (isConnectionRefused(err) || isConnectionError(err))) {
      const user = await runWithBase(alt);
      _cachedProfileIsolationUser.set(idx, user);
      return user;
    }
    throw err;
  }
}

/**
 * Single-flight map: parallel workers/tests often call ensureE2ESubscriptionForUser for the same
 * (baseUrl, email) at once — duplicate login + POST bursts saturate the API and surface as
 * ECONNRESET / "fetch failed" in logs. Coalesce to one in-flight promise per key.
 */
const _subscriptionEnsureInFlight = new Map<string, Promise<void>>();

/** Ensure E2E test user's tenant has active subscription and VERIFIED KYC (enables asset create, marketplace publish, etc.) */
async function ensureE2ESubscriptionForUser(user: TestUser, baseUrl: string = API_BASE_URL): Promise<void> {
  if (isSubscriptionPrimedForBaseUrl(baseUrl)) {
    return;
  }

  const dedupeKey = `${baseUrl}::${user.email}`;
  const existing = _subscriptionEnsureInFlight.get(dedupeKey);
  if (existing) {
    return existing;
  }

  const run = (async (): Promise<void> => {
    try {
      await withRetry(async () => {
        const loginRes = await fetch(`${baseUrl}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: user.email, password: user.password }),
        });
        if (!loginRes.ok) {
          // 400 = bad credentials during setup race; 429 = rate limited — both transient
          if (loginRes.status === 429 || loginRes.status >= 500) {
            throw new Error(`Subscription ensure login failed: ${loginRes.status}`);
          }
          console.log(`⚠️ ensureE2ESubscription: login returned ${loginRes.status}, skipping`);
          return;
        }
        const loginData = (await loginRes.json()) as { access_token?: string };
        // Phase 220.4: when USE_HTTPONLY_AUTH_COOKIES is enabled, the
        // access_token lives in a Set-Cookie header, not in the body.
        const setCookie = loginRes.headers.get('set-cookie') ?? '';
        const cookieMatch = setCookie.match(/(?:^|,\s*)access_token=([^;,]+)/i);
        const token = loginData.access_token ?? cookieMatch?.[1] ?? '';
        if (!token) {
          console.log(
            '⚠️ ensureE2ESubscription: no access_token in body or Set-Cookie. ' +
            `Set-Cookie header: ${setCookie.slice(0, 120)}`,
          );
          return;
        }
        const ensureRes = await fetch(`${baseUrl}/test/ensure-e2e-subscription/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            ...e2eTestHeaders(),
          },
        });
        if (ensureRes.ok) {
          console.log('✅ E2E subscription ensured');
        } else if (ensureRes.status === 404) {
          // Endpoint doesn't exist (prod build) — skip silently
          return;
        } else if (ensureRes.status >= 500 || ensureRes.status === 429) {
          // Transient server error — retry
          throw new Error(`Subscription ensure endpoint failed: ${ensureRes.status}`);
        } else {
          const body = await ensureRes.text().catch(() => '');
          console.log(
            `⚠️ ensureE2ESubscription: ensure endpoint returned ${ensureRes.status}: ${body.slice(0, 200)}`
          );
        }
      }, 'E2E subscription ensure');
    } finally {
      _subscriptionEnsureInFlight.delete(dedupeKey);
    }
  })();

  _subscriptionEnsureInFlight.set(dedupeKey, run);
  return run;
}

/** True when API indicates email is already registered (backend: "Email address is already registered") */
function isAlreadyRegisteredError(errorData: unknown): boolean {
  if (!errorData || typeof errorData !== 'object') return false;
  const o = errorData as Record<string, unknown>;
  // Check common error response fields: message, detail (DRF), error.message, code
  const msg = typeof o.message === 'string' ? o.message : '';
  const detail = typeof o.detail === 'string' ? o.detail : '';
  const code = typeof o.code === 'string' ? o.code : '';
  const details = o.error && typeof o.error === 'object' ? (o.error as Record<string, unknown>) : o;
  const emailDetails =
    details.details && typeof details.details === 'object'
      ? (details.details as Record<string, unknown>).email
      : undefined;
  const emailArr = Array.isArray(emailDetails) ? emailDetails : [];
  const hasAlready = (s: string) => /already\s+(registered|exists)|EMAIL_ALREADY_EXISTS/i.test(s);
  if (hasAlready(msg)) return true;
  if (hasAlready(detail)) return true;
  if (hasAlready(code)) return true;
  return emailArr.some((m) => typeof m === 'string' && hasAlready(m));
}

/** Per-worker cache for consumer user */
let _cachedConsumerUser: TestUser | null = null;

/**
 * Create or get consumer test user for E2E tests (different tenant for purchasing)
 * Cached per worker to reduce API load.
 * On connection error, tries alternate port 8000 <-> 8001.
 */
export async function ensureConsumerTestUser(): Promise<TestUser> {
  if (_cachedConsumerUser) return _cachedConsumerUser;

  const email = 'e2e_consumer@example.com';
  const password = 'TestPass123'; // Must contain uppercase, lowercase, and number
  const name = 'E2E Consumer User';

  const runWithBase = async (baseUrl: string): Promise<TestUser> => {
    let loginResult = await withRetry(async () => {
      const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (loginResponse.ok) {
        console.log('✅ Consumer test user exists and can login');
        return { email, password, name } as TestUser;
      }
      // 429 = rate-limited: user may exist but we can't verify — throw so withRetry retries
      if (loginResponse.status === 429) {
        throw new Error('Rate limited (429); will retry');
      }
      return null;
    }, 'Consumer test user login');

    if (!loginResult) {
      await runEnsureE2EUserRoles();
      loginResult = await withRetry(async () => {
        const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (loginResponse.ok) return { email, password, name } as TestUser;
        if (loginResponse.status === 429) {
          throw new Error('Rate limited (429); will retry');
        }
        return null;
      }, 'Consumer test user login (retry after ensure)');
    }

    if (loginResult) {
      await ensureE2ESubscriptionForUser(loginResult, baseUrl);
      return loginResult;
    }

    const registered = await withRetry(async () => {
      console.log('Consumer test user login failed, attempting to create user...');
      const registerResponse = await fetch(`${baseUrl}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      });

      if (registerResponse.ok) {
        console.log('✅ Consumer test user created successfully');
        return { email, password, name };
      }
      // Intentional fallback: malformed JSON (e.g. HTML error page) -> empty object for error parsing
      const errorData = await registerResponse.json().catch(() => ({}));
      if ((registerResponse.status === 400 || registerResponse.status === 409) && isAlreadyRegisteredError(errorData)) {
        console.log('⚠️  Consumer test user already registered, using existing credentials');
        return { email, password, name };
      }
      const errMsg =
        typeof (errorData as { error?: { message?: string } })?.error?.message === 'string'
          ? (errorData as { error: { message: string } }).error.message
          : '';
      const isHostResolutionError =
        registerResponse.status === 500 &&
        /translate host name|name resolution|getaddrinfo|ENOTFOUND|could not translate/i.test(errMsg);
      if (isHostResolutionError) {
        throw new Error(
          `Backend at ${baseUrl.replace(/\/api\/v1\/?$/, '')} cannot resolve host "postgres". ` +
            'E2E requires the API to run inside Docker (api-service) so it can reach postgres.'
        );
      }
      throw new Error(
        `Consumer registration failed: ${registerResponse.status} - ${JSON.stringify(errorData)}`
      );
    }, 'Consumer test user register');
    await ensureE2ESubscriptionForUser(registered, baseUrl);
    return registered;
  };

  try {
    const user = await runWithBase(API_BASE_URL);
    _cachedConsumerUser = user;
    return user;
  } catch (err) {
    const alt = getAlternateApiBase(API_BASE_URL);
    if (alt && (isConnectionRefused(err) || isConnectionError(err))) {
      try {
        const user = await runWithBase(alt);
        _cachedConsumerUser = user;
        return user;
      } catch {
        // Fall through to rethrow original
      }
    }
    throw err;
  }
}

/**
 * Per-worker cache for persona logins. Avoids redundant API login calls
 * that exhaust rate limits when many persona tests run sequentially.
 */
const _cachedPersonaUsers = new Map<string, TestUser>();

/** E2E persona user credentials (must match hub ensure_e2e_user_roles) */
const E2E_PERSONA_USERS: Record<string, TestUser> = {
  tenant_admin: {
    email: 'e2e_admin@example.com',
    password: 'TestPass123',
    name: 'E2E Tenant Admin',
  },
  platform_admin: {
    email: 'e2e_platform@example.com',
    password: 'TestPass123',
    name: 'E2E Platform Admin',
  },
  auditor: {
    email: 'e2e_auditor@example.com',
    password: 'TestPass123',
    name: 'E2E Auditor',
  },
  compliance_officer: {
    email: 'e2e_cpo@example.com',
    password: 'TestPass123',
    name: 'E2E Compliance Officer',
  },
  external_developer: {
    email: 'e2e_developer@example.com',
    password: 'TestPass123',
    name: 'E2E External Developer',
  },
  data_mesh_domain_owner: {
    email: 'e2e_dmo@example.com',
    password: 'TestPass123',
    name: 'E2E Data Mesh Domain Owner',
  },
};

const FETCH_TIMEOUT_MS = 15000;

/** Try login against a specific base URL */
async function tryLoginWithBase(user: TestUser, baseUrl: string): Promise<boolean> {
  const url = `${baseUrl.replace(/\/$/, '')}/auth/login/`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, password: user.password }),
      signal: controller.signal,
    });
    // 429 = rate-limited: user may exist but we can't verify — throw so withRetry retries
    if (r.status === 429) {
      throw new Error('Rate limited (429); will retry');
    }
    return r.ok;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function tryLogin(user: TestUser): Promise<boolean> {
  const attempt = async (baseUrl: string): Promise<boolean> =>
    withRetry(
      () => tryLoginWithBase(user, baseUrl),
      `Login ${user.email} (${baseUrl})`
    );

  try {
    return await attempt(API_BASE_URL);
  } catch (err) {
    // On connection error, try alternate port (8000 <-> 8001) before giving up
    const alt = getAlternateApiBase(API_BASE_URL);
    if (alt && (isConnectionError(err) || isConnectionRefused(err))) {
      try {
        return await attempt(alt);
      } catch {
        // Improve error message: backend not reachable on either port
        const msg =
          err instanceof Error ? err.message : String(err);
        const cause = err && typeof err === 'object' && (err as { cause?: Error }).cause;
        const causeMsg = cause instanceof Error ? cause.message : '';
        throw new Error(
          `API unreachable at ${API_BASE_URL} and ${alt}. ` +
            `Ensure backend is running: docker compose -f docker-compose.test.yml up -d api-service-test (port 8001) or docker compose up -d api-service (port 8000). ` +
            `Original: ${msg}${causeMsg ? ` [cause: ${causeMsg}]` : ''}`
        );
      }
    }
    // 401/403: user not found or wrong credentials
    if (!isConnectionError(err) && !isConnectionRefused(err)) {
      return false;
    }
    throw err;
  }
}

const E2E_CONTAINERS = ['hub-test-api', 'hub-api', 'hub-dev-api'] as const;

/**
 * Register a persona user via API on remote environments where docker exec is unavailable.
 * Returns true if the user was created or already exists, false on failure.
 */
async function registerPersonaViaApi(user: TestUser, baseUrl: string = API_BASE_URL): Promise<boolean> {
  try {
    const registerResponse = await fetch(`${baseUrl}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, password: user.password, name: user.name }),
    });
    if (registerResponse.ok) {
      console.log(`✅ Persona user ${user.email} registered via API`);
      return true;
    }
    const errorData = await registerResponse.json().catch(() => ({}));
    if ((registerResponse.status === 400 || registerResponse.status === 409) && isAlreadyRegisteredError(errorData)) {
      return true; // Already exists
    }
    const body = JSON.stringify(errorData).slice(0, 300);
    console.warn(`⚠️ Persona registration for ${user.email} failed: ${registerResponse.status} ${body}`);
    return false;
  } catch {
    return false;
  }
}

/** Run ensure_e2e_user_roles via docker exec; used when persona user login fails.
 *  Skips entirely for remote APIs — docker exec is unavailable against deployed environments. */
async function runEnsureE2EUserRoles(): Promise<boolean> {
  if (_isRemoteApi) return false;

  const { execSync } = await import('child_process');
  const port = new URL(API_BASE_URL).port || '8000';
  const preferred = port === '8001' ? 'hub-test-api' : 'hub-api';
  const containers = [preferred, ...E2E_CONTAINERS.filter((c) => c !== preferred)];

  for (const container of containers) {
    try {
      execSync(`docker exec ${container} python hub/manage.py ensure_e2e_user_roles`, {
        stdio: 'pipe',
        encoding: 'utf8',
      });
      await new Promise((r) => setTimeout(r, 2000)); // Allow DB to settle
      return true;
    } catch {
      // Try next container
    }
  }
  return false;
}

/**
 * Ensure tenant admin test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 * Retries on connection errors (ECONNRESET, fetch failed) to handle backend overload.
 */
export async function ensureTenantAdminUser(): Promise<TestUser> {
  const cached = _cachedPersonaUsers.get('tenant_admin');
  if (cached) return cached;
  const user = E2E_PERSONA_USERS.tenant_admin;
  const maxAttempts = 3;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      let ok = await tryLogin(user);
      if (!ok) {
        if (_isRemoteApi) {
          await registerPersonaViaApi(user);
        } else {
          await runEnsureE2EUserRoles();
        }
        await new Promise((r) => setTimeout(r, 3000));
        ok = await tryLogin(user);
      }
      if (ok) {
        await ensureE2ESubscriptionForUser(user);
        _cachedPersonaUsers.set('tenant_admin', user);
        return user;
      }
    } catch (err) {
      if (isConnectionError(err) && attempt < maxAttempts - 1) {
        if (!_isRemoteApi) await runEnsureE2EUserRoles();
        await new Promise((r) => setTimeout(r, 4000 * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
  throw new Error(
    _isRemoteApi
      ? `Tenant admin user '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
      : `Tenant admin user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure platform admin test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensurePlatformAdminUser(): Promise<TestUser> {
  const cached = _cachedPersonaUsers.get('platform_admin');
  if (cached) return cached;
  const user = E2E_PERSONA_USERS.platform_admin;
  let ok = await tryLogin(user);
  if (!ok) {
    if (_isRemoteApi) {
      await registerPersonaViaApi(user);
    } else {
      await runEnsureE2EUserRoles();
    }
    await new Promise((r) => setTimeout(r, 2000));
    ok = await tryLogin(user);
  }
  if (ok) { _cachedPersonaUsers.set('platform_admin', user); return user; }
  throw new Error(
    _isRemoteApi
      ? `Platform admin user '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
      : `Platform admin user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure auditor test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureAuditorUser(): Promise<TestUser> {
  const cached = _cachedPersonaUsers.get('auditor');
  if (cached) return cached;
  const user = E2E_PERSONA_USERS.auditor;
  let ok = await tryLogin(user);
  if (!ok) {
    if (_isRemoteApi) {
      await registerPersonaViaApi(user);
    } else {
      await runEnsureE2EUserRoles();
    }
    await new Promise((r) => setTimeout(r, 2000));
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    _cachedPersonaUsers.set('auditor', user);
    return user;
  }
  throw new Error(
    _isRemoteApi
      ? `Auditor user '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
      : `Auditor user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure compliance officer test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureComplianceOfficerUser(): Promise<TestUser> {
  const cached = _cachedPersonaUsers.get('compliance_officer');
  if (cached) return cached;
  const user = E2E_PERSONA_USERS.compliance_officer;
  let ok = await tryLogin(user);
  if (!ok) {
    let ensured: boolean;
    if (_isRemoteApi) {
      ensured = await registerPersonaViaApi(user);
    } else {
      ensured = await runEnsureE2EUserRoles();
    }
    await new Promise((r) => setTimeout(r, 2000));
    ok = await tryLogin(user);
    if (!ok && !ensured) {
      throw new Error(
        _isRemoteApi
          ? `Compliance officer '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
          : `Compliance officer user not found and ensure_e2e_user_roles failed (docker may be unavailable). Run manually: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
      );
    }
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    _cachedPersonaUsers.set('compliance_officer', user);
    return user;
  }
  throw new Error(
    _isRemoteApi
      ? `Compliance officer '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
      : `Compliance officer user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure external developer test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureExternalDeveloperUser(): Promise<TestUser> {
  const cached = _cachedPersonaUsers.get('external_developer');
  if (cached) return cached;
  const user = E2E_PERSONA_USERS.external_developer;
  let ok = await tryLogin(user);
  if (!ok) {
    if (_isRemoteApi) {
      await registerPersonaViaApi(user);
    } else {
      await runEnsureE2EUserRoles();
    }
    await new Promise((r) => setTimeout(r, 2000));
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    _cachedPersonaUsers.set('external_developer', user);
    return user;
  }
  throw new Error(
    _isRemoteApi
      ? `External developer '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
      : `External developer user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure data mesh domain owner test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureDataMeshDomainOwnerUser(): Promise<TestUser> {
  const cached = _cachedPersonaUsers.get('data_mesh_domain_owner');
  if (cached) return cached;
  const user = E2E_PERSONA_USERS.data_mesh_domain_owner;
  let ok = await tryLogin(user);
  if (!ok) {
    if (_isRemoteApi) {
      await registerPersonaViaApi(user);
    } else {
      await runEnsureE2EUserRoles();
    }
    await new Promise((r) => setTimeout(r, 2000));
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    _cachedPersonaUsers.set('data_mesh_domain_owner', user);
    return user;
  }
  throw new Error(
    _isRemoteApi
      ? `Data mesh domain owner '${user.email}' not found on remote. Seed with: kubectl exec -n hub-staging deploy/hub-staging-api -- python hub/manage.py ensure_e2e_user_roles`
      : `Data mesh domain owner user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}
