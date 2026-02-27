/**
 * Create Test User Setup
 * Creates a test user via API for E2E tests
 */

// Node fetch needs absolute URL; VITE_API_BASE_URL is relative (/api/v1)
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  'http://localhost:8000/api/v1';

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

const FETCH_RETRIES = 4;
const RETRY_DELAYS_MS = [2000, 4000, 6000, 8000];

/** Run fn with retries on transient connection errors */
async function withRetry<T>(fn: () => Promise<T>, label: string): Promise<T> {
  let lastError: unknown;
  for (let i = 0; i < FETCH_RETRIES; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (i < FETCH_RETRIES - 1 && isConnectionError(error)) {
        const delay = RETRY_DELAYS_MS[i];
        console.log(
          `⚠️ ${label} failed (connection error), retrying in ${delay}ms (attempt ${i + 1}/${FETCH_RETRIES})...`
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

  const email = 'e2e_test@example.com';
  const password = 'TestPass123'; // Must contain uppercase, lowercase, and number
  const name = 'E2E Test User';

  const runWithBase = async (baseUrl: string): Promise<TestUser> => {
    const loginResult = await withRetry(async () => {
      const loginResponse = await fetch(`${baseUrl}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (loginResponse.ok) {
        console.log('✅ Test user exists and can login');
        return { email, password, name } as TestUser;
      }
      return null;
    }, 'Test user login');

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
      if (registerResponse.status === 400 && isAlreadyRegisteredError(errorData)) {
        console.log('⚠️  Test user already registered, using existing credentials');
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
            'E2E requires the API to run inside Docker (api-service) so it can reach postgres. ' +
            'Start the stack: docker compose -f docker-compose.dev.yml up -d and ensure no process on the host is bound to port 8000.'
        );
      }
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

/** Ensure E2E test user's tenant has active subscription and VERIFIED KYC (enables asset create, marketplace publish, etc.) */
async function ensureE2ESubscriptionForUser(user: TestUser, baseUrl: string = API_BASE_URL): Promise<void> {
  try {
    const loginRes = await fetch(`${baseUrl}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, password: user.password }),
    });
    if (!loginRes.ok) return;
    const loginData = (await loginRes.json()) as { access_token?: string };
    const token = loginData.access_token;
    if (!token) return;
    const ensureRes = await fetch(`${baseUrl}/test/ensure-e2e-subscription/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    if (ensureRes.ok) {
      console.log('✅ E2E subscription ensured');
    }
  } catch {
    // Ignore - endpoint may not exist in prod; tests will skip or fail with clear message
  }
}

/** True when API indicates email is already registered (backend: "Email address is already registered") */
function isAlreadyRegisteredError(errorData: unknown): boolean {
  if (!errorData || typeof errorData !== 'object') return false;
  const o = errorData as Record<string, unknown>;
  const msg = typeof o.message === 'string' ? o.message : '';
  const details = o.error && typeof o.error === 'object' ? (o.error as Record<string, unknown>) : o;
  const emailDetails =
    details.details && typeof details.details === 'object'
      ? (details.details as Record<string, unknown>).email
      : undefined;
  const emailArr = Array.isArray(emailDetails) ? emailDetails : [];
  const hasAlready = (s: string) => /already\s+(registered|exists)/i.test(s);
  if (hasAlready(msg)) return true;
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
      if (registerResponse.status === 400 && isAlreadyRegisteredError(errorData)) {
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
      } catch (altErr) {
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

/** Run ensure_e2e_user_roles via docker exec; used when persona user login fails. */
async function runEnsureE2EUserRoles(): Promise<boolean> {
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
 */
export async function ensureTenantAdminUser(): Promise<TestUser> {
  const user = E2E_PERSONA_USERS.tenant_admin;
  let ok = await tryLogin(user);
  if (!ok) {
    await runEnsureE2EUserRoles();
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    return user;
  }
  throw new Error(
    `Tenant admin user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure platform admin test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensurePlatformAdminUser(): Promise<TestUser> {
  const user = E2E_PERSONA_USERS.platform_admin;
  let ok = await tryLogin(user);
  if (!ok) {
    await runEnsureE2EUserRoles();
    ok = await tryLogin(user);
  }
  if (ok) return user;
  throw new Error(
    `Platform admin user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure auditor test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureAuditorUser(): Promise<TestUser> {
  const user = E2E_PERSONA_USERS.auditor;
  let ok = await tryLogin(user);
  if (!ok) {
    await runEnsureE2EUserRoles();
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    return user;
  }
  throw new Error(
    `Auditor user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure compliance officer test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureComplianceOfficerUser(): Promise<TestUser> {
  const user = E2E_PERSONA_USERS.compliance_officer;
  let ok = await tryLogin(user);
  if (!ok) {
    const ensured = await runEnsureE2EUserRoles();
    ok = await tryLogin(user);
    if (!ok && !ensured) {
      throw new Error(
        `Compliance officer user not found and ensure_e2e_user_roles failed (docker may be unavailable). ` +
          `Run manually: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
      );
    }
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    return user;
  }
  throw new Error(
    `Compliance officer user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure external developer test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureExternalDeveloperUser(): Promise<TestUser> {
  const user = E2E_PERSONA_USERS.external_developer;
  let ok = await tryLogin(user);
  if (!ok) {
    await runEnsureE2EUserRoles();
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    return user;
  }
  throw new Error(
    `External developer user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}

/**
 * Ensure data mesh domain owner test user exists and can login.
 * Retries after running ensure_e2e_user_roles if login fails (handles global setup race).
 */
export async function ensureDataMeshDomainOwnerUser(): Promise<TestUser> {
  const user = E2E_PERSONA_USERS.data_mesh_domain_owner;
  let ok = await tryLogin(user);
  if (!ok) {
    await runEnsureE2EUserRoles();
    ok = await tryLogin(user);
  }
  if (ok) {
    await ensureE2ESubscriptionForUser(user);
    return user;
  }
  throw new Error(
    `Data mesh domain owner user not found. Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
  );
}
