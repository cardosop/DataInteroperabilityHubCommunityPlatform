/**
 * E2E API helpers for creating backend resources (e.g. assets) without UI.
 * Used so tests that require an asset (e.g. JOURNEY-DPO-002 publish) don't skip when catalog is empty.
 * No mocks; real backend only.
 */

import type { TestUser } from '../setup/create-test-user';

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

/**
 * Get or create one asset via API for the given user (same tenant). Returns the asset id.
 * Tries to use an existing asset first to avoid plan limit issues.
 * Use before tests that need at least one asset (e.g. marketplace publish, scheduled export).
 * Retries on transient connection errors (other side closed, ECONNRESET).
 * @param ensureActivated - when true, ensures asset is ACTIVE (for marketplace publish which requires ACTIVE)
 */
export async function createAssetViaApi(
  user: TestUser,
  options?: { ensureActivated?: boolean }
): Promise<string> {
  let lastErr: unknown;
  for (let r = 0; r < RETRIES; r++) {
    try {
      return await createAssetViaApiOnce(user, options);
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
  options?: { ensureActivated?: boolean }
): Promise<string> {
  const token = await loginViaApi(user);

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
  const data = (await response.json()) as { id?: string; version?: number };
  if (!data.id) {
    throw new Error('Create asset response missing id');
  }
  const assetId = data.id;

  if (options?.ensureActivated) {
    // E2E helper: ensure activation prerequisites and activate
    const prereqRes = await fetch(
      `${API_BASE_URL}/assets/${assetId}/ensure-e2e-activation-prerequisites/`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!prereqRes.ok) {
      if (prereqRes.status === 404) {
        throw new Error(
          'E2E activation prerequisites endpoint not available (404). ' +
            'Rebuild api-service-test: docker compose -f docker-compose.test.yml build api-service-test --no-cache'
        );
      }
      const err = await prereqRes.text();
      throw new Error(`E2E activation prerequisites failed: ${prereqRes.status} ${err}`);
    }
    if (prereqRes.ok) {
      const actRes = await fetch(`${API_BASE_URL}/assets/${assetId}/activate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ version: data.version ?? 1 }),
      });
      if (!actRes.ok) {
        const err = await actRes.text();
        throw new Error(`Asset activation failed: ${actRes.status} ${err}`);
      }
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
      } catch (error) {
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
export async function createRetentionPolicyViaApi(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);

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
 * Tries to use an existing export first. Creates one with asset_ids if none found.
 * Use before tests that need at least one scheduled export (e.g. edit page).
 */
export async function createScheduledExportViaApi(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);

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

  const assetId = await createAssetViaApi(user);
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
      source_scope: { asset_ids: [assetId] },
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
 */
export async function createDatasetViaApi(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);

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
    if (datasets[0]?.id) return datasets[0].id;
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

  if (!initResponse.ok) {
    const body = await initResponse.text().catch(() => '');
    throw new Error(`File init API failed: ${initResponse.status} ${body}`);
  }

  const initData = (await initResponse.json()) as { file_id?: string; id?: string; upload_url?: string };
  const fileId = initData.file_id ?? initData.id;
  if (!fileId) throw new Error('File init response missing file_id');

  // Upload to presigned URL (may point to MinIO; replace host for localhost reachability)
  const uploadUrl = initData.upload_url;
  if (uploadUrl) {
    try {
      const putRes = await fetch(uploadUrl, {
        method: 'PUT',
        body: csvContent,
        headers: { 'Content-Type': 'text/csv' },
      });
      if (!putRes.ok) {
        // Try with localhost if URL uses docker hostname (e2e runs on host)
        const url = new URL(uploadUrl);
        if (url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
          const localUrl = `http://localhost:${url.port || '9010'}${url.pathname}${url.search}`;
          const localPutRes = await fetch(localUrl, {
            method: 'PUT',
            body: csvContent,
            headers: { 'Content-Type': 'text/csv' },
          });
          if (!localPutRes.ok) {
            throw new Error(`Upload failed: ${localPutRes.status}`);
          }
        } else {
          throw new Error(`Upload failed: ${putRes.status}`);
        }
      }
    } catch (err) {
      // In test/dev mode backend may allow complete without storage; continue
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
    body: JSON.stringify({ file_id: fileId }),
  });

  if (!datasetResponse.ok) {
    const body = await datasetResponse.text().catch(() => '');
    throw new Error(`Create dataset API failed: ${datasetResponse.status} ${body}`);
  }

  const datasetData = (await datasetResponse.json()) as { id?: string };
  if (!datasetData.id) throw new Error('Create dataset response missing id');
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

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`createODPSProductViaApi failed: ${response.status} ${body}`);
  }

  // The ODPS upload flow creates a workflow; poll for the contract id
  const createData = (await response.json()) as {
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
