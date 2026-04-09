/**
 * E2E API helpers for DQ and compliance runs.
 * Follows the same pattern as api-assets.ts — real backend only, no mocks.
 */

import type { TestUser } from '../setup/create-test-user';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

function isTransientConnectionError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  if (/fetch failed|terminated|network/i.test(msg)) return true;
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'ECONNRESET' || c.code === 'UND_ERR_SOCKET') return true;
  }
  return false;
}

const RETRIES = 5;
const RETRY_DELAYS_MS = [2000, 4000, 6000, 8000, 10000];

async function loginViaApiCompliance(user: TestUser): Promise<string> {
  for (let r = 0; r < RETRIES; r++) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: user.password }),
      });
      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('retry-after') ?? '', 10);
        const backoffMs = retryAfter > 0 ? retryAfter * 1000 : RETRY_DELAYS_MS[Math.min(r, RETRY_DELAYS_MS.length - 1)];
        await new Promise((resolve) => setTimeout(resolve, backoffMs));
        continue;
      }
      if (response.status >= 500 && r < RETRIES - 1) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      if (!response.ok) {
        const body = await response.text().catch(() => '');
        throw new Error(`Login failed: ${response.status} ${body}`);
      }
      const data = (await response.json()) as { access_token?: string };
      if (!data.access_token) throw new Error('Login response missing access_token');
      return data.access_token;
    } catch (err) {
      if (r < RETRIES - 1 && isTransientConnectionError(err)) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      if (r >= RETRIES - 1) throw err;
    }
  }
  throw new Error('loginViaApiCompliance: exhausted retries');
}

export interface DQRunResult {
  status: string;
  run_id?: string;
  result_summary?: Record<string, unknown>;
  issues?: Record<string, unknown>[];
}

export interface ComplianceRunResult {
  status: string;
  run_id?: string;
  issues?: Record<string, unknown>[];
  // Phase 213.G.10 — surface the error fields the backend now persists.
  // `error` is the human-readable message (REMOTE_FAILURE / EXECUTION_ERROR),
  // `errorType` is the canonical taxonomy slot, and `errorCode` is the
  // machine-readable code from the POLL_TIMEOUT path (metadata_json).
  error?: string;
  errorType?: string;
  errorCode?: string;
}

/**
 * Trigger a DQ run via API. Calls POST /dq/runs/.
 * At least one of assetId or datasetId must be provided.
 * Returns the run ID.
 */
export async function triggerDQRunViaApi(
  user: TestUser,
  params: { assetId?: string; datasetId?: string; fileId?: string }
): Promise<string> {
  const token = await loginViaApiCompliance(user);
  const body: Record<string, string> = {};
  if (params.assetId) body.asset_id = params.assetId;
  if (params.datasetId) body.dataset_id = params.datasetId;
  if (params.fileId) body.file_id = params.fileId;

  const endpoints = ['/dq/runs/', '/dq-runs/', '/data-quality/runs/'];
  for (const endpoint of endpoints) {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    if (resp.status === 404) continue;
    if (!resp.ok) {
      const bodyText = await resp.text().catch(() => '');
      throw new Error(`triggerDQRunViaApi failed: ${resp.status} ${bodyText}`);
    }
    const data = (await resp.json()) as { id?: string; run_id?: string };
    const runId = data.id || data.run_id;
    if (!runId) throw new Error('DQ run response missing id');
    return runId;
  }
  throw new Error('triggerDQRunViaApi: no valid endpoint found');
}

/**
 * Poll a DQ run until it reaches a terminal state (SUCCEEDED, FAILED, ERROR, CANCELLED).
 * Calls GET /dq/runs/{runId}/ in a loop.
 * Returns the run result. Throws if timeout is reached.
 */
export async function waitForDQRunViaApi(
  user: TestUser,
  runId: string,
  timeoutMs = 120_000
): Promise<DQRunResult> {
  const token = await loginViaApiCompliance(user);
  const terminalStates = new Set([
    'SUCCEEDED', 'FAILED', 'ERROR', 'CANCELLED', 'COMPLETED', 'PASSED',
  ]);

  const endpoints = [`/dq/runs/${runId}/`, `/dq-runs/${runId}/`, `/data-quality/runs/${runId}/`];
  const startMs = Date.now();

  while (Date.now() - startMs < timeoutMs) {
    for (const endpoint of endpoints) {
      const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => null);
      if (!resp || resp.status === 404) continue;
      if (!resp.ok) break;

      const data = (await resp.json()) as {
        status?: string;
        id?: string;
        result_summary?: Record<string, unknown>;
        issues?: Record<string, unknown>[];
      };
      const status = data.status?.toUpperCase() ?? '';
      if (terminalStates.has(status)) {
        return { status, run_id: runId, result_summary: data.result_summary, issues: data.issues };
      }
      // Not terminal — wait and retry
      break;
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error(
    `waitForDQRunViaApi: run ${runId} did not reach terminal state within ${timeoutMs}ms`
  );
}

/**
 * Trigger a compliance run via API. Calls POST /compliance/runs/.
 * Returns the run ID.
 */
export async function triggerComplianceRunViaApi(
  user: TestUser,
  params: { assetId?: string; datasetId?: string; fileId?: string }
): Promise<string> {
  const token = await loginViaApiCompliance(user);
  const body: Record<string, string> = {};
  if (params.assetId) body.asset_id = params.assetId;
  if (params.datasetId) body.dataset_id = params.datasetId;
  if (params.fileId) body.file_id = params.fileId;

  const endpoints = ['/compliance/runs/', '/compliance-runs/'];
  for (const endpoint of endpoints) {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    if (resp.status === 404) continue;
    if (!resp.ok) {
      const bodyText = await resp.text().catch(() => '');
      throw new Error(`triggerComplianceRunViaApi failed: ${resp.status} ${bodyText}`);
    }
    const data = (await resp.json()) as { id?: string; run_id?: string };
    const runId = data.id || data.run_id;
    if (!runId) throw new Error('Compliance run response missing id');
    return runId;
  }
  throw new Error('triggerComplianceRunViaApi: no valid endpoint found');
}

/**
 * Poll a compliance run until it reaches a terminal state.
 * Returns the run result. Throws if timeout is reached.
 */
export async function waitForComplianceRunViaApi(
  user: TestUser,
  runId: string,
  timeoutMs = 120_000
): Promise<ComplianceRunResult> {
  const token = await loginViaApiCompliance(user);
  const terminalStates = new Set([
    'SUCCEEDED', 'FAILED', 'ERROR', 'CANCELLED', 'COMPLETED', 'PASSED',
  ]);

  const endpoints = [
    `/compliance/runs/${runId}/`,
    `/compliance-runs/${runId}/`,
  ];
  const startMs = Date.now();

  while (Date.now() - startMs < timeoutMs) {
    for (const endpoint of endpoints) {
      const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => null);
      if (!resp || resp.status === 404) continue;
      if (!resp.ok) break;

      const data = (await resp.json()) as {
        status?: string;
        issues?: Record<string, unknown>[];
        regulation_mapping_json?: {
          error?: string;
          error_type?: string;
        } | null;
        metadata_json?: {
          error_code?: string;
        } | null;
      };
      const status = data.status?.toUpperCase() ?? '';
      if (terminalStates.has(status)) {
        // Phase 213.G.10 — surface error fields so a FAILED run produces
        // a one-shot diagnosable message in the test output (instead of
        // the historical bare "Status was 'FAILED'" form).
        const mapping = data.regulation_mapping_json ?? undefined;
        const metadata = data.metadata_json ?? undefined;
        return {
          status,
          run_id: runId,
          issues: data.issues,
          error: mapping?.error,
          errorType: mapping?.error_type,
          errorCode: metadata?.error_code,
        };
      }
      break;
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error(
    `waitForComplianceRunViaApi: run ${runId} did not reach terminal state within ${timeoutMs}ms`
  );
}

/**
 * Phase 213.G.13 — assert a compliance run reached SUCCEEDED, and on
 * failure produce a one-shot diagnosable message that includes the
 * canonical error_type AND whichever of (error | error_code) is
 * populated. Replaces the historical bare ``Status was 'FAILED'`` form
 * which discarded every diagnostic field even when the backend had it.
 *
 * Throws a `Error` (so Playwright's expect.poll / `test.fail` paths
 * still work). Returns void on success.
 */
export function expectComplianceRunSucceeded(
  result: ComplianceRunResult,
  context?: string
): void {
  const okStatuses = new Set(['SUCCEEDED', 'COMPLETED', 'PASSED']);
  if (okStatuses.has(result.status)) return;

  const parts: string[] = [];
  if (context) parts.push(context);
  parts.push(`status=${result.status}`);
  if (result.errorType) parts.push(`error_type=${result.errorType}`);
  if (result.error) {
    parts.push(`error=${result.error}`);
  } else if (result.errorCode) {
    parts.push(`error_code=${result.errorCode}`);
  } else {
    parts.push(
      'error=<NONE PERSISTED — backend invariant violated: every FAILED ' +
        'ComplianceRun must have regulation_mapping_json.error or ' +
        'metadata_json.error_code>'
    );
  }
  throw new Error(`Compliance run did not succeed — ${parts.join(' ')}`);
}
