/**
 * E2E API helpers for creating backend resources (e.g. assets) without UI.
 * Used so tests that require an asset (e.g. JOURNEY-DPO-002 publish) don't skip when catalog is empty.
 * No mocks; real backend only.
 */

import type { TestUser } from '../setup/create-test-user';
import { e2eTestHeaders } from './e2e-token';
import type { CleanupRegistry } from './test-data-cleanup';

// Node fetch needs absolute URL; VITE_API_BASE_URL is relative (/api/v1)
// Prefer 8001 when E2E_WEB_PORT set (test stack uses 8001)
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
let API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

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

const RETRIES = 5;
const RETRY_DELAYS_MS = [2000, 4000, 6000, 8000, 10000];

/**
 * Log in via API and return access token.
 * Retries on transient connection errors (other side closed, ECONNRESET),
 * 429 rate limiting, and transient 500s.
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
        if (response.status === 429) {
          // Rate-limited: backoff and retry (parallel E2E workers saturate the limiter)
          const retryAfter = parseInt(response.headers.get('retry-after') ?? '', 10);
          const backoffMs = (retryAfter > 0 ? retryAfter * 1000 : RETRY_DELAYS_MS[Math.min(r, RETRY_DELAYS_MS.length - 1)]);
          await new Promise((resolve) => setTimeout(resolve, backoffMs));
          continue;
        }
        if (response.status >= 500 && r < RETRIES - 1) {
          // Transient server error: retry with backoff
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
          continue;
        }
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
        if (r >= RETRIES - 1) throw err;
      }
    }
  }
  throw lastErr;
}

/**
 * Fetch the `key` field of an existing asset by id via Node.js API call.
 * Returns null when the asset cannot be fetched (not a fatal error — caller decides).
 * Used by the duplicate-key test to retrieve a known key without a browser-context fetch
 * (which would fail due to CORS: frontend origin ≠ backend origin in E2E).
 */
export async function getAssetKeyViaApi(user: TestUser, assetId: string): Promise<string | null> {
  const token = await loginViaApi(user);
  const res = await fetch(`${API_BASE_URL}/assets/${assetId}/`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  } as RequestInit).catch(() => null);
  if (!res || !res.ok) return null;
  const data = (await res.json()) as { key?: string };
  return data.key ?? null;
}

/** Linked asset UUID for a contract (Node-side API; no browser CORS). */
export async function getContractLinkedAssetIdViaApi(
  user: TestUser,
  contractId: string
): Promise<string | null> {
  const token = await loginViaApi(user);
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  } as RequestInit).catch(() => null);
  if (!res || !res.ok) return null;
  const data = (await res.json()) as { asset?: string | null };
  const aid = data.asset;
  return typeof aid === 'string' && aid.length > 0 ? aid : null;
}

/**
 * Get or create one asset via API for the given user (same tenant). Returns the asset id.
 * Tries to use an existing asset first to avoid plan limit issues.
 * Use before tests that need at least one asset (e.g. marketplace publish, scheduled export).
 * Retries on transient connection errors (other side closed, ECONNRESET).
 * @param ensureActivated - when true, ensures asset is ACTIVE (for marketplace publish which requires ACTIVE)
 * @param forceNew - when true, always creates a brand-new asset (never reuses existing). Use in
 *   tests that mutate status (retire/delete) to avoid interfering with parallel test workers that
 *   may be operating on the same asset.
 */
export async function createAssetViaApi(
  user: TestUser,
  options?: { ensureActivated?: boolean; forceNew?: boolean; cleanup?: CleanupRegistry }
): Promise<string> {
  let lastErr: unknown;
  for (let r = 0; r < RETRIES; r++) {
    try {
      const id = await createAssetViaApiOnce(user, options);
      // Phase 213.C — auto-track for per-test teardown when a cleanup registry is supplied.
      // Helpers used by reuse-paths (existing asset returned by list query) are tracked too:
      // teardown is idempotent (404 = already gone) and the soft-delete tombstone is harmless.
      options?.cleanup?.track({ type: 'asset', id, owner: user });
      return id;
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

async function createAssetViaApiOnce(
  user: TestUser,
  options?: { ensureActivated?: boolean; forceNew?: boolean }
): Promise<string> {
  const token = await loginViaApi(user);

  // When forceNew is set, skip the reuse logic entirely so each call gets a unique asset.
  // This is required for tests that mutate status (retire/delete): two parallel workers
  // operating on the same asset cause version conflicts and race-condition skips.
  if (!options?.forceNew) {
    // First, try to get an existing ACTIVE asset to avoid plan limit issues
    const listResponse = await fetch(
      `${API_BASE_URL}/assets/?limit=20${options?.ensureActivated ? '&status=ACTIVE' : ''}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (listResponse.ok) {
      const listData = (await listResponse.json()) as
        | { results?: Array<{ id?: string; status?: string }> }
        | Array<{ id?: string; status?: string }>;
      const assets = Array.isArray(listData) ? listData : listData.results || [];
      const suitable = options?.ensureActivated
        ? assets.find((a) => a.status === 'ACTIVE' && a.id)
        : assets[0];
      if (suitable?.id) return suitable.id;
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
      // Attempt to re-ensure subscription and retry once
      const reEnsureRes = await fetch(`${API_BASE_URL}/test/ensure-e2e-subscription/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          ...e2eTestHeaders(),
        },
      }).catch(() => null);
      if (reEnsureRes?.ok) {
        console.log('✅ E2E subscription re-ensured after 403, retrying asset creation');
        const retryResponse = await fetch(`${API_BASE_URL}/assets/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ key, name: 'E2E Publish Asset', description: 'Created by E2E for publish tests', visibility: 'INTERNAL' }),
        });
        if (retryResponse.ok) {
          const retryData = (await retryResponse.json()) as { id?: string };
          if (retryData.id) {
            const retryAssetId = retryData.id;
            if (options?.ensureActivated) {
              await fetch(`${API_BASE_URL}/assets/${retryAssetId}/activate/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify({ version: 1 }),
              }).catch(() => null);
            }
            return retryAssetId;
          }
        }
      }
      throw new Error(
        `Create asset API failed: 403 subscription_inactive. ` +
          `Ensure E2E subscription: run 'docker exec hub-test-api python hub/manage.py ensure_e2e_subscription' or use npm run test:e2e (calls ensure endpoint automatically).`
      );
    }
    throw new Error(`Create asset API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string; version?: number };
  if (!data.id) {
    throw new Error('Create asset response missing id');
  }
  const assetId = data.id;

  if (options?.ensureActivated) {
    // E2E helper: ensure activation prerequisites and activate.
    // Retry the helper up to 3 times on 5xx (transient backend error under parallel E2E load).
    let prereqRes: Response | null = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      prereqRes = await fetch(
        `${API_BASE_URL}/assets/${assetId}/ensure-e2e-activation-prerequisites/`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (prereqRes.ok || prereqRes.status === 404) break;
      if (prereqRes.status >= 500 && attempt < 2) {
        // Transient 5xx — wait and retry
        await new Promise((resolve) => setTimeout(resolve, (attempt + 1) * 3000));
        continue;
      }
      if (prereqRes.status < 500) {
        const err = await prereqRes.text();
        throw new Error(`E2E activation prerequisites failed: ${prereqRes.status} ${err}`);
      }
      // 5xx after all retries — fall through to manual flow below
      break;
    }
    // When helper is unavailable (404) or returned 5xx after all retries, attempt manual contract
    // flow as a best-effort prerequisite. Failures are non-fatal: some backends allow asset
    // activation without ACTIVE contracts (or workflow restrictions block manual status changes).
    if (!prereqRes!.ok) {
      try {
        const contractJson = {
          apiVersion: 'odcs.io/v3.0.0',
          kind: 'DataContract',
          id: `e2e-activate-${Date.now()}`,
          name: 'E2E Activation Contract',
          version: '1.0.0',
          schema: { fields: [{ name: 'id', type: 'string' }, { name: 'name', type: 'string' }] },
        };
        const contractRes = await fetch(`${API_BASE_URL}/contracts/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            asset_id: assetId,
            original_spec_type: 'ODCS',
            original_spec_version: '3.0.0',
            original_format: 'JSON',
            original_raw: JSON.stringify(contractJson),
          }),
        });
        if (contractRes.ok) {
          const contract = (await contractRes.json()) as { id?: string; version?: number };
          const contractId = contract.id;
          if (contractId) {
            let contractVersion = contract.version ?? 1;
            // Trigger validation (best-effort; ignore failures)
            await fetch(`${API_BASE_URL}/contracts/${contractId}/validate/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ async: false }),
            }).catch(() => null);
            // Poll until VALID + NORMALIZED (max 30 × 2s = 60s)
            for (let i = 0; i < 30; i++) {
              await new Promise((r) => setTimeout(r, 2000));
              const check = await fetch(`${API_BASE_URL}/contracts/${contractId}/`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (check.ok) {
                const contractData = (await check.json()) as {
                  validation_status?: string;
                  normalization_status?: string;
                  version?: number;
                };
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
            // PATCH contract to ACTIVE (best-effort; workflows may block this — non-fatal)
            await fetch(`${API_BASE_URL}/contracts/${contractId}/`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ status: 'ACTIVE', version: contractVersion }),
            }).catch(() => null);
            // Allow backend to propagate before asset activation
            await new Promise((r) => setTimeout(r, 3000));
          }
        }
        // If contract creation failed (workflows disabled, plan limits), proceed without contracts.
        // Asset activation may still succeed (some backends allow activation without contracts).
      } catch {
        // Best-effort fallback failed entirely — proceed to activation anyway
      }
    }

    // Allow backend to propagate prerequisites before activating (avoid race condition)
    await new Promise((r) => setTimeout(r, 2000));

    // Prerequisites met (via helper or manual flow) — re-fetch asset version and activate.
    // Re-fetch is required: prerequisites may bump the version and activating with a stale
    // version causes a 400 conflict error.
    // Retry on 400 (stale version race): re-fetch version and retry once.
    let activateVersion = data.version ?? 1;
    for (let activateAttempt = 0; activateAttempt < 2; activateAttempt++) {
      const assetCheckRes = await fetch(`${API_BASE_URL}/assets/${assetId}/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (assetCheckRes.ok) {
        const assetData = (await assetCheckRes.json()) as { version?: number };
        activateVersion = assetData.version ?? activateVersion;
      }
      const actRes = await fetch(`${API_BASE_URL}/assets/${assetId}/activate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ version: activateVersion }),
      });
      if (actRes.ok) break;
      if (actRes.status === 400 && activateAttempt === 0) {
        // Stale version — wait 2s and retry with fresh version
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      const err = await actRes.text();
      // Already ACTIVE is acceptable (idempotent)
      if (/already active|asset is already/i.test(err)) break;
      // Non-fatal: backend may require contracts or have workflow restrictions.
      // Return the assetId in its current state; the caller can handle non-ACTIVE status.
      break;
    }
  }
  return assetId;
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
      } catch {
        // Ignore deletion errors - continue cleaning up others
      }
    }
  }
}

/**
 * Create or get one retention policy via API for the given user.
 * Tries to use an existing policy first. Creates one with asset_id if none found.
 * Use before tests that need at least one retention policy (e.g. edit page).
 */
export async function createRetentionPolicyViaApi(
  user: TestUser,
  options?: { forceNew?: boolean }
): Promise<string> {
  const token = await loginViaApi(user);

  if (!options?.forceNew) {
    const listResponse = await fetch(`${API_BASE_URL}/governance/retention-policies/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    if (listResponse.ok) {
      const listData = (await listResponse.json()) as { results?: Array<{ id?: string }> };
      const policies = listData.results ?? [];
      if (policies[0]?.id) return policies[0].id;
    }
  }

  const assetId = await createAssetViaApi(user);
  const name = `e2e-rp-${Date.now()}`;
  const response = await fetch(`${API_BASE_URL}/governance/retention-policies/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name,
      asset_id: assetId,
      policy_type: 'TIME_BASED',
      retention_period_days: 30,
      action: 'SOFT_DELETE',
      enabled: true,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Create retention policy API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) throw new Error('Create retention policy response missing id');
  return data.id;
}

/**
 * Create or get one scheduled export via API for the given user.
 * Tries to use an existing export (with dataset_ids scope) first.
 * Creates one with dataset_ids if none found — dataset_ids scope is directly supported
 * by the Prefect flow; asset_ids scope requires resolution and asset must have datasets.
 * Use before tests that need at least one scheduled export (e.g. edit page).
 */
export async function createScheduledExportViaApi(
  user: TestUser,
  options?: { forceNew?: boolean }
): Promise<string> {
  const token = await loginViaApi(user);

  if (!options?.forceNew) {
    const listResponse = await fetch(`${API_BASE_URL}/scheduled-exports/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    if (listResponse.ok) {
      const listData = (await listResponse.json()) as { results?: Array<{ id?: string }> };
      const exports = listData.results ?? [];
      if (exports[0]?.id) return exports[0].id;
    }
  }

  // Create an asset with a linked dataset so the flow can resolve items to export.
  // Using dataset_ids in source_scope avoids the asset→dataset resolution step
  // and guarantees the flow finds at least one item (items_found >= 1).
  const assetId = await createAssetViaApi(user, { forceNew: true });
  const datasetId = await createDatasetViaApi(user, { assetId, forceNew: true });

  const name = `e2e-se-${Date.now()}`;
  const response = await fetch(`${API_BASE_URL}/scheduled-exports/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name,
      schedule_config: { cron: '0 2 * * *', timezone: 'UTC' },
      destination_type: 'S3',
      destination_config: { bucket: 'e2e-test-bucket' },
      source_scope: { dataset_ids: [datasetId] },
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Create scheduled export API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) throw new Error('Create scheduled export response missing id');
  return data.id;
}

/**
 * Get first ODCS contract ID via API for the given user.
 * Returns null if no ODCS contract exists (ODPS Link page requires ODCS contract).
 */
export async function getODCSContractIdViaApi(user: TestUser): Promise<string | null> {
  const token = await loginViaApi(user);

  const response = await fetch(
    `${API_BASE_URL}/contracts/?spec_type=ODCS&page_size=10`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) return null;
  const data = (await response.json()) as { results?: Array<{ id?: string }> };
  const contracts = data.results ?? [];
  return contracts[0]?.id ?? null;
}

/**
 * Create or get one dataset via API for the given user.
 * Tries to use an existing dataset first. Creates one (file + dataset) if none found.
 * Use before tests that need at least one dataset (e.g. dataset edit, Link to Asset).
 *
 * @param options.assetId - when provided, returns/creates a dataset linked to this asset
 * @param options.forceNew - when true, always creates a brand-new dataset (never reuses existing).
 *   Use in tests that require specific state (e.g. no asset_id) to avoid returning a reused
 *   dataset that may already have different state from a prior test run.
 */
export async function createDatasetViaApi(user: TestUser, options?: { assetId?: string; forceNew?: boolean; cleanup?: CleanupRegistry }): Promise<string> {
  const token = await loginViaApi(user);

  // When forceNew is set, skip the reuse logic entirely — always create a fresh dataset.
  // Required for tests that assert on specific dataset state (e.g. no asset linked).
  if (!options?.forceNew) {
    // If assetId is provided, look for an existing dataset already linked to that asset.
    // Note: the ?asset= filter is not supported by the API, so we must verify the asset field manually.
    if (options?.assetId) {
      const listResponse = await fetch(`${API_BASE_URL}/datasets/?page_size=50`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });
      if (listResponse.ok) {
        const listData = (await listResponse.json()) as { results?: Array<{ id?: string; file?: string; asset?: string }> };
        // Only reuse a dataset that is actually linked to this specific asset
        const linked = (listData.results ?? []).find((d) => d.file && d.asset === options.assetId);
        if (linked?.id) {
          options?.cleanup?.track({ type: 'dataset', id: linked.id, owner: user });
          return linked.id;
        }
      }
    } else {
      const listResponse = await fetch(`${API_BASE_URL}/datasets/?page_size=10`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });
      if (listResponse.ok) {
        const listData = (await listResponse.json()) as { results?: Array<{ id?: string }> };
        const datasets = listData.results ?? [];
        if (datasets[0]?.id) {
          options?.cleanup?.track({ type: 'dataset', id: datasets[0].id, owner: user });
          return datasets[0].id;
        }
      }
    }
  }

  // Create file via init + complete, then create dataset
  const csvContent = 'id,name\n1,test\n2,sample';
  const contentSha256 = await sha256Hex(csvContent);

  const initResponse = await fetch(`${API_BASE_URL}/files/init/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name: `e2e-dataset-${Date.now()}.csv`,
      content_type: 'text/csv',
      size: Buffer.byteLength(csvContent, 'utf-8'),
      upload_method: 'browser',
    }),
  });

  let effectiveInitResponse = initResponse;
  if (!initResponse.ok) {
    const body = await initResponse.text().catch(() => '');
    if (initResponse.status === 403 && /subscription_inactive|No active subscription/i.test(body)) {
      // Re-ensure subscription and retry
      await fetch(`${API_BASE_URL}/test/ensure-e2e-subscription/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          ...e2eTestHeaders(),
        },
      }).catch(() => null);
      const retryInit = await fetch(`${API_BASE_URL}/files/init/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: `e2e-dataset-${Date.now()}.csv`,
          content_type: 'text/csv',
          size: Buffer.byteLength(csvContent, 'utf-8'),
          upload_method: 'browser',
        }),
      });
      if (!retryInit.ok) {
        throw new Error(`File init API failed after subscription re-ensure: ${retryInit.status}`);
      }
      effectiveInitResponse = retryInit;
    } else {
      throw new Error(`File init API failed: ${initResponse.status} ${body}`);
    }
  }

  const initData = (await effectiveInitResponse.json()) as { file_id?: string; id?: string; upload_url?: string };
  const fileId = initData.file_id ?? initData.id;
  if (!fileId) throw new Error('File init response missing file_id');

  // Upload to the presigned URL. The upload MUST succeed before we call
  // /complete/ — otherwise the file row exists in the DB but the bytes are
  // missing from S3, and every downstream test (compliance scan, DQ run,
  // dataset preview) will then fail mysteriously with "file not found" or
  // hit a fail-closed timeout. Previously this block silently swallowed
  // any upload error ("backend may allow complete without storage"); that
  // hid the staging-broken AWS_S3_ENDPOINT_URL bug for weeks and showed up
  // as flaky compliance/DQ runs.
  //
  // For docker-compose dev where the API hands out a presigned URL signed
  // for the in-network `minio:9000` host, we still rewrite to localhost so
  // the host-side e2e runner can reach MinIO — but failures from that
  // rewrite are now propagated, not swallowed.
  const uploadUrl = initData.upload_url;
  if (!uploadUrl) {
    throw new Error('File init response missing upload_url — cannot upload');
  }

  const tryPut = async (url: string): Promise<Response> =>
    fetch(url, {
      method: 'PUT',
      body: csvContent,
      headers: { 'Content-Type': 'text/csv' },
    });

  let putRes = await tryPut(uploadUrl).catch((err) => {
    throw new Error(`Upload network error to ${uploadUrl}: ${err}`);
  });

  if (!putRes.ok) {
    const parsed = new URL(uploadUrl);
    const isInternalHost =
      parsed.hostname !== 'localhost' &&
      parsed.hostname !== '127.0.0.1' &&
      // Only attempt the localhost rewrite for docker-compose-style hostnames;
      // a real AWS S3 endpoint (`*.amazonaws.com`) failing must surface as-is.
      !parsed.hostname.endsWith('.amazonaws.com');
    if (isInternalHost) {
      const localUrl = `http://localhost:${parsed.port || '9010'}${parsed.pathname}${parsed.search}`;
      putRes = await tryPut(localUrl).catch((err) => {
        throw new Error(`Upload network error to ${localUrl} (rewrite of ${uploadUrl}): ${err}`);
      });
    }
    if (!putRes.ok) {
      const body = await putRes.text().catch(() => '');
      throw new Error(
        `File upload to object store failed: ${putRes.status} ${putRes.statusText} — ${body.slice(0, 300)}`
      );
    }
  }

  const completeResponse = await fetch(`${API_BASE_URL}/files/${fileId}/complete/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content_sha256: contentSha256 }),
  });

  if (!completeResponse.ok) {
    const body = await completeResponse.text().catch(() => '');
    throw new Error(`File complete API failed: ${completeResponse.status} ${body}`);
  }

  const datasetResponse = await fetch(`${API_BASE_URL}/datasets/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      file_id: fileId,
      ...(options?.assetId ? { asset_id: options.assetId } : {}),
    }),
  });

  if (!datasetResponse.ok) {
    const body = await datasetResponse.text().catch(() => '');
    throw new Error(`Create dataset API failed: ${datasetResponse.status} ${body}`);
  }

  const datasetData = (await datasetResponse.json()) as { id?: string };
  if (!datasetData.id) throw new Error('Create dataset response missing id');
  // Phase 213.C — auto-track for per-test teardown. Datasets hard-delete (audit confirmed).
  options?.cleanup?.track({ type: 'dataset', id: datasetData.id, owner: user });
  return datasetData.id;
}

async function sha256Hex(text: string): Promise<string> {
  const { createHash } = await import('node:crypto');
  return createHash('sha256').update(text, 'utf-8').digest('hex');
}

/**
 * Create or get one ODPS product via API for the given user.
 * Tries to reuse an existing ODPS contract (original_spec_type=ODPS) first.
 * Creates a minimal but valid ODPS product with an embedded ODCS contract if none found.
 * Returns the contract id of the ODPS product.
 *
 * Use before tests that need at least one ODPS product (e.g. JOURNEY-DPO-017 export).
 */
export async function createODPSProductViaApi(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);

  // Try to reuse an existing ODPS contract
  const listRes = await fetch(`${API_BASE_URL}/contracts/?page_size=20`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  if (listRes.ok) {
    const listData = (await listRes.json()) as { results?: Array<{ id?: string; original_spec_type?: string }> };
    const existing = (listData.results ?? []).find(
      (c) => c.original_spec_type === 'ODPS' && c.id
    );
    if (existing?.id) return existing.id;
  }

  // Create a minimal valid ODPS product with embedded ODCS contract
  const productId = `e2e-odps-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const odcsId = `e2e-odcs-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const odpsPayload = {
    schema: 'https://opendataproducts.org/schema/v4.1',
    version: '4.1',
    product: {
      details: {
        en: {
          productID: productId,
          name: 'E2E ODPS Product',
          description: 'Minimal ODPS product created by E2E API fixture for export tests',
          productVersion: '1.0.0',
        },
      },
      dataSchema: {
        fields: [
          { name: 'id', type: 'string' },
          { name: 'value', type: 'number' },
        ],
      },
      contract: {
        spec: {
          apiVersion: 'odcs.io/v3.0.2',
          kind: 'DataContract',
          id: odcsId,
          name: 'E2E ODCS Contract (embedded in ODPS)',
          version: '1.0.0',
          description: 'Embedded ODCS contract for E2E ODPS export test',
          schema: {
            fields: [
              { name: 'id', type: 'string', nullable: false, description: 'ID' },
              { name: 'value', type: 'number', nullable: true, description: 'Value' },
            ],
          },
        },
      },
    },
  };

  const response = await fetch(`${API_BASE_URL}/contracts/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      original_raw: JSON.stringify(odpsPayload),
      original_format: 'JSON',
      original_spec_type: 'ODPS',
    }),
  });

  let effectiveResponse = response;
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    if (response.status === 403 && /subscription_inactive|No active subscription/i.test(body)) {
      await fetch(`${API_BASE_URL}/test/ensure-e2e-subscription/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          ...e2eTestHeaders(),
        },
      }).catch(() => null);
      const retryRes = await fetch(`${API_BASE_URL}/contracts/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          original_raw: JSON.stringify(odpsPayload),
          original_format: 'JSON',
          original_spec_type: 'ODPS',
        }),
      });
      if (!retryRes.ok) {
        const retryBody = await retryRes.text().catch(() => '');
        throw new Error(`createODPSProductViaApi failed after subscription re-ensure: ${retryRes.status} ${retryBody}`);
      }
      effectiveResponse = retryRes;
    } else {
      throw new Error(`createODPSProductViaApi failed: ${response.status} ${body}`);
    }
  }

  // The ODPS upload flow creates a workflow; poll for the contract id
  const createData = (await effectiveResponse.json()) as {
    id?: string;
    workflow_instance_id?: string;
    odps_contract?: { id?: string };
  };

  // Direct create returns contract id
  if (createData.id) return createData.id;

  // Workflow-based create: poll workflow status for the ODPS contract id
  if (createData.workflow_instance_id) {
    const workflowId = createData.workflow_instance_id;
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      const statusRes = await fetch(
        `${API_BASE_URL}/contracts/odps/workflow-status/${workflowId}/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (statusRes.ok) {
        const statusData = (await statusRes.json()) as {
          status?: string;
          odps_contract?: { id?: string };
        };
        if (statusData.status === 'COMPLETED' && statusData.odps_contract?.id) {
          return statusData.odps_contract.id;
        }
        if (statusData.status === 'FAILED') {
          throw new Error(`createODPSProductViaApi: workflow failed`);
        }
      }
    }
    throw new Error(`createODPSProductViaApi: workflow did not complete within 60s`);
  }

  throw new Error('createODPSProductViaApi: response missing id and workflow_instance_id');
}

/**
 * Create a minimal ODPS contract linked to a new asset (linked-asset UI on ODPS detail).
 * Returns the hub contract id (use /odps/:id in the SPA when applicable).
 */
export async function createODPSContractLinkedToAssetViaApi(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);
  const assetId = await createAssetViaApi(user);

  const productId = `e2e-odps-asset-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const odcsId = `e2e-odcs-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const odpsPayload = {
    schema: 'https://opendataproducts.org/schema/v4.1',
    version: '4.1',
    product: {
      details: {
        en: {
          productID: productId,
          name: 'E2E ODPS Product (linked asset)',
          description: 'Minimal ODPS with asset_id for contract-asset-link E2E',
          productVersion: '1.0.0',
        },
      },
      dataSchema: {
        fields: [
          { name: 'id', type: 'string' },
          { name: 'value', type: 'number' },
        ],
      },
      contract: {
        spec: {
          apiVersion: 'odcs.io/v3.0.2',
          kind: 'DataContract',
          id: odcsId,
          name: 'E2E ODCS Contract (embedded in ODPS)',
          version: '1.0.0',
          description: 'Embedded ODCS for linked-asset E2E',
          schema: {
            fields: [
              { name: 'id', type: 'string', nullable: false, description: 'ID' },
              { name: 'value', type: 'number', nullable: true, description: 'Value' },
            ],
          },
        },
      },
    },
  };

  const response = await fetch(`${API_BASE_URL}/contracts/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      original_raw: JSON.stringify(odpsPayload),
      original_format: 'JSON',
      original_spec_type: 'ODPS',
      asset_id: assetId,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`createODPSContractLinkedToAssetViaApi failed: ${response.status} ${body}`);
  }

  const createData = (await response.json()) as {
    id?: string;
    workflow_instance_id?: string;
    odps_contract?: { id?: string };
  };

  if (createData.id) return createData.id;

  if (createData.workflow_instance_id) {
    const workflowId = createData.workflow_instance_id;
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      const statusRes = await fetch(
        `${API_BASE_URL}/contracts/odps/workflow-status/${workflowId}/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (statusRes.ok) {
        const statusData = (await statusRes.json()) as {
          status?: string;
          odps_contract?: { id?: string };
        };
        if (statusData.status === 'COMPLETED' && statusData.odps_contract?.id) {
          return statusData.odps_contract.id;
        }
        if (statusData.status === 'FAILED') {
          throw new Error(`createODPSContractLinkedToAssetViaApi: workflow failed`);
        }
      }
    }
    throw new Error(`createODPSContractLinkedToAssetViaApi: workflow did not complete within 60s`);
  }

  throw new Error('createODPSContractLinkedToAssetViaApi: response missing id and workflow_instance_id');
}

/**
 * Create or get one ODCS contract via API for the given user.
 * Tries to use an existing ODCS contract first. Creates one if none found.
 * Use before tests that need an ODCS contract (e.g. ODPS Link page).
 */
export async function createODCSContractViaApi(user: TestUser): Promise<string> {
  const existing = await getODCSContractIdViaApi(user);
  if (existing) return existing;

  const token = await loginViaApi(user);
  const assetId = await createAssetViaApi(user);

  const odcsContract = {
    apiVersion: 'odcs.io/v3.0.2',
    kind: 'DataContract',
    id: `e2e-odcs-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: 'E2E ODCS Contract for ODPS Link',
    version: '1.0.0',
    description: 'Minimal ODCS contract for E2E ODPS Link tests',
    schema: {
      fields: [
        { name: 'id', type: 'string', nullable: false, description: 'Unique identifier' },
      ],
    },
  };

  const response = await fetch(`${API_BASE_URL}/contracts/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      original_raw: JSON.stringify(odcsContract),
      original_format: 'JSON',
      original_spec_type: 'ODCS',
      asset_id: assetId,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Create ODCS contract API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) throw new Error('Create ODCS contract response missing id');
  return data.id;
}

/**
 * Create or get one scheduled ingestion via API for the given user.
 * Tries to reuse an existing e2e scheduled ingestion first. Creates one if none found.
 * Follows the same pattern as createScheduledExportViaApi.
 * Use before tests that need an existing scheduled ingestion (e.g. edit, delete journey tests).
 */
export async function createScheduledIngestionViaApi(
  user: TestUser,
  options?: { forceNew?: boolean; poolIndex?: number }
): Promise<string> {
  const token = await loginViaApi(user);

  if (!options?.forceNew) {
    const listResponse = await fetch(`${API_BASE_URL}/scheduled-ingestions/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    if (listResponse.ok) {
      const listData = (await listResponse.json()) as { results?: Array<{ id?: string; name?: string }> };
      const ingestions = Array.isArray(listData) ? listData : (listData.results ?? []);
      // Prefer reusing an existing e2e ingestion to avoid plan limits.
      // poolIndex allows different test projects to pick different pool items to prevent
      // concurrent projects from racing over the same resource.
      const e2eIngestions = ingestions.filter((i) => i.name?.startsWith('e2e-si-'));
      const idx = options?.poolIndex ?? 0;
      const candidate = e2eIngestions[idx] ?? e2eIngestions[0] ?? ingestions[0];
      if (candidate?.id) return candidate.id;
    }
  }

  const assetId = await createAssetViaApi(user);
  const name = `e2e-si-${Date.now()}`;

  const payload = {
    name,
    schedule_config: { cron: '0 3 * * *', timezone: 'UTC' },
    source_type: 'S3',
    source_config: { bucket: 'e2e-test-bucket', prefix: 'e2e/' },
    target_asset_id: assetId,
    test_connection: false, // Skip connection test (matches ScheduledIngestionCreatePage UI behaviour)
    file_pattern: '.*',
  };

  const response = await fetch(`${API_BASE_URL}/scheduled-ingestions/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Create scheduled ingestion API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) throw new Error('Create scheduled ingestion response missing id');
  return data.id;
}
