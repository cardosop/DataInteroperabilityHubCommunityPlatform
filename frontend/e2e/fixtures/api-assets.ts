/**
 * E2E API helpers for creating backend resources (e.g. assets) without UI.
 * Used so tests that require an asset (e.g. JOURNEY-DPO-002 publish) don't skip when catalog is empty.
 * No mocks; real backend only.
 */

import type { TestUser } from '../setup/create-test-user';

// Node fetch needs absolute URL; VITE_API_BASE_URL is relative (/api/v1)
let API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  'http://localhost:8000/api/v1';

/** True when error is ECONNREFUSED (wrong port or backend not running). */
function isConnectionRefused(err: unknown): boolean {
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  return !!(
    cause &&
    typeof cause === 'object' &&
    (cause as { code?: string }).code === 'ECONNREFUSED'
  );
}

/** True when error is a transient connection failure (retryable): other side closed, ECONNRESET, etc. */
function isTransientConnectionError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  if (/fetch failed|terminated|network/i.test(msg)) return true;
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'ECONNRESET' || c.code === 'UND_ERR_SOCKET') return true;
    if (typeof c.message === 'string' && /other side closed|socket hang up/i.test(c.message))
      return true;
  }
  return false;
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

const RETRIES = 3;
const RETRY_DELAYS_MS = [2000, 4000, 6000];

/**
 * Log in via API and return access token.
 * Retries on transient connection errors (other side closed, ECONNRESET).
 * Tries alternate port (8000 <-> 8001) on ECONNREFUSED.
 */
async function loginViaApi(user: TestUser): Promise<string> {
  const basesToTry = [API_BASE_URL];
  const alt = getAlternateApiBase(API_BASE_URL);
  if (alt) basesToTry.push(alt);

  let lastErr: unknown;
  for (const tryBase of basesToTry) {
    for (let r = 0; r < RETRIES; r++) {
      try {
        const response = await fetch(`${tryBase}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: user.email, password: user.password }),
        });
        if (!response.ok) {
          const body = await response.text().catch(() => '');
          throw new Error(`Login API failed: ${response.status} ${body}`);
        }
        const data = (await response.json()) as { access_token?: string };
        if (!data.access_token) {
          throw new Error('Login response missing access_token');
        }
        API_BASE_URL = tryBase; // Use working base for subsequent fetches
        return data.access_token;
      } catch (err) {
        lastErr = err;
        if (r < RETRIES - 1 && isTransientConnectionError(err)) {
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
          continue;
        }
        if (isConnectionRefused(err)) {
          break; // Try alternate port
        }
        throw err;
      }
    }
  }
  throw lastErr;
}

/**
 * Get or create one asset via API for the given user (same tenant). Returns the asset id.
 * Tries to use an existing asset first to avoid plan limit issues.
 * Use before tests that need at least one asset (e.g. marketplace publish, scheduled export).
 * Retries on transient connection errors (other side closed, ECONNRESET).
 */
export async function createAssetViaApi(user: TestUser): Promise<string> {
  let lastErr: unknown;
  for (let r = 0; r < RETRIES; r++) {
    try {
      return await createAssetViaApiOnce(user);
    } catch (err) {
      lastErr = err;
      if (r < RETRIES - 1 && isTransientConnectionError(err)) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      throw err;
    }
  }
  throw lastErr;
}

async function createAssetViaApiOnce(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);

  // First, try to get an existing asset to avoid plan limit issues
  const listResponse = await fetch(`${API_BASE_URL}/assets/?limit=1`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  if (listResponse.ok) {
    const listData = (await listResponse.json()) as
      | { results?: Array<{ id?: string }> }
      | Array<{ id?: string }>;
    // Handle both paginated ({ results: [...] }) and non-paginated ([...]) responses
    const assets = Array.isArray(listData) ? listData : listData.results || [];
    if (assets.length > 0 && assets[0].id) {
      return assets[0].id;
    }
  }

  // If no existing asset found, try to create a new one
  const key = `e2e-publish-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const response = await fetch(`${API_BASE_URL}/assets/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      key,
      name: 'E2E Publish Asset',
      description: 'Created by E2E for publish tests',
      visibility: 'INTERNAL',
    }),
  });
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    if (response.status === 403 && /subscription_inactive|No active subscription/i.test(body)) {
      throw new Error(
        `Create asset API failed: 403 subscription_inactive. ` +
          `Ensure E2E subscription: run 'docker exec hub-test-api python hub/manage.py ensure_e2e_subscription' or use npm run test:e2e (calls ensure endpoint automatically).`
      );
    }
    throw new Error(`Create asset API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) {
    throw new Error('Create asset response missing id');
  }
  return data.id;
}

/**
 * Clean up old E2E scheduled exports to avoid plan limit issues.
 * Deletes scheduled exports with names starting with "e2e-se-".
 * Use before tests that need to create a new scheduled export.
 */
export async function cleanupOldScheduledExports(user: TestUser): Promise<void> {
  const token = await loginViaApi(user);

  // List all scheduled exports
  const listResponse = await fetch(`${API_BASE_URL}/scheduled-exports/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  if (!listResponse.ok) {
    // If listing fails, continue - this is not critical
    return;
  }

  const listData = (await listResponse.json()) as {
    results?: Array<{ id?: string; name?: string }>;
  };
  const exports = Array.isArray(listData) ? listData : listData.results || [];

  // Delete old E2E test scheduled exports
  for (const exportItem of exports) {
    if (exportItem.id && exportItem.name && exportItem.name.startsWith('e2e-se-')) {
      try {
        await fetch(`${API_BASE_URL}/scheduled-exports/${exportItem.id}/`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (error) {
        // Ignore deletion errors - continue cleaning up others
      }
    }
  }
}
