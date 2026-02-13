/**
 * Create Test User Setup
 * Creates a test user via API for E2E tests
 */

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface TestUser {
  email: string;
  password: string;
  name: string;
}

/** True when error is a transient connection/network failure (retryable) */
function isConnectionError(error: unknown): boolean {
  if (error instanceof TypeError && error.message === 'fetch failed') return true;
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

const FETCH_RETRIES = 3;
const RETRY_DELAYS_MS = [2000, 4000, 6000];

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

/**
 * Create or get test user for E2E tests
 */
export async function ensureTestUser(): Promise<TestUser> {
  const email = 'e2e_test@example.com';
  const password = 'TestPass123'; // Must contain uppercase, lowercase, and number
  const name = 'E2E Test User';

  // Try to login first (user might already exist), with retry on connection errors
  const loginResult = await withRetry(async () => {
    const loginResponse = await fetch(`${API_BASE_URL}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (loginResponse.ok) {
      console.log('✅ Test user exists and can login');
      return { email, password, name } as TestUser;
    }
    return null;
  }, 'Test user login').catch(() => null);

  if (loginResult) return loginResult;

  // Login failed, try to create user (with retry on connection errors)
  return withRetry(async () => {
    console.log('Test user login failed, attempting to create user...');
    const registerResponse = await fetch(`${API_BASE_URL}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });

    if (registerResponse.ok) {
      console.log('✅ Test user created successfully');
      return { email, password, name };
    }
    const errorData = await registerResponse.json().catch(() => ({}));
    if (registerResponse.status === 400 && isAlreadyRegisteredError(errorData)) {
      console.log('⚠️  Test user already registered, using existing credentials');
      return { email, password, name };
    }
    const errMsg =
      typeof (errorData as { error?: { message?: string } })?.error?.message === 'string'
        ? (errorData as { error: { message: string } }).error.message
        : '';
    if (
      registerResponse.status === 500 &&
      /postgres|translate host name|name resolution/i.test(errMsg)
    ) {
      throw new Error(
        `Backend at ${API_BASE_URL.replace(/\/api\/v1\/?$/, '')} cannot resolve host "postgres". ` +
          'E2E requires the API to run inside Docker (api-service) so it can reach postgres. ' +
          'Start the stack: docker compose -f docker-compose.dev.yml up -d and ensure no process on the host is bound to port 8000.'
      );
    }
    throw new Error(
      `Registration failed: ${registerResponse.status} - ${JSON.stringify(errorData)}`
    );
  }, 'Test user register');
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

/**
 * Create or get consumer test user for E2E tests (different tenant for purchasing)
 */
export async function ensureConsumerTestUser(): Promise<TestUser> {
  const email = 'e2e_consumer@example.com';
  const password = 'TestPass123'; // Must contain uppercase, lowercase, and number
  const name = 'E2E Consumer User';

  const loginResult = await withRetry(async () => {
    const loginResponse = await fetch(`${API_BASE_URL}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (loginResponse.ok) {
      console.log('✅ Consumer test user exists and can login');
      return { email, password, name } as TestUser;
    }
    return null;
  }, 'Consumer test user login').catch(() => null);

  if (loginResult) return loginResult;

  return withRetry(async () => {
    console.log('Consumer test user login failed, attempting to create user...');
    const registerResponse = await fetch(`${API_BASE_URL}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });

    if (registerResponse.ok) {
      console.log('✅ Consumer test user created successfully');
      return { email, password, name };
    }
    const errorData = await registerResponse.json().catch(() => ({}));
    if (registerResponse.status === 400 && isAlreadyRegisteredError(errorData)) {
      console.log('⚠️  Consumer test user already registered, using existing credentials');
      return { email, password, name };
    }
    const errMsg =
      typeof (errorData as { error?: { message?: string } })?.error?.message === 'string'
        ? (errorData as { error: { message: string } }).error.message
        : '';
    if (
      registerResponse.status === 500 &&
      /postgres|translate host name|name resolution/i.test(errMsg)
    ) {
      throw new Error(
        `Backend at ${API_BASE_URL.replace(/\/api\/v1\/?$/, '')} cannot resolve host "postgres". ` +
          'E2E requires the API to run inside Docker (api-service) so it can reach postgres. ' +
          'Start the stack: docker compose -f docker-compose.dev.yml up -d and ensure no process on the host is bound to port 8000.'
      );
    }
    throw new Error(
      `Consumer registration failed: ${registerResponse.status} - ${JSON.stringify(errorData)}`
    );
  }, 'Consumer test user register');
}
