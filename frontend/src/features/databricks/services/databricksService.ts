/**
 * Databricks control-plane API service — task 0.15.
 *
 * Client for /api/v1/databricks/workspaces/ (+ nested credentials).
 *
 * Wire contract (mirrors warehouseService + the backend handler):
 *  - list endpoints are DRF-paginated ({count, ..., results}) — normalized
 *    at this boundary so pages never crash on `map is not a function`,
 *  - errors carry the standardized envelope {"error": {"code", "message"}};
 *    the machine-readable CODE is preserved on DatabricksApiError so the
 *    UI can render distinct surfaces (e.g. the flag-disabled banner).
 */
import { apiClient } from '@/shared/api/client';
import type {
  DatabricksCredential,
  DatabricksCredentialCreatePayload,
  DatabricksTestResult,
  DatabricksWorkspace,
  DatabricksWorkspaceCreatePayload,
} from '@/shared/types/databricks';

const BASE = '/api/v1/databricks';

/** Standardized API error with the machine-readable code preserved. */
export class DatabricksApiError extends Error {
  readonly code?: string;
  readonly httpStatus?: number;

  constructor(message: string, code?: string, httpStatus?: number) {
    super(message);
    this.name = 'DatabricksApiError';
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    headers: {
      ...apiClient._buildHeaders(init?.method ?? 'GET', `${BASE}${url}`),
    },
    ...init,
  });
  const body = (await resp.json().catch(() => ({}))) as Record<string, unknown>;
  if (!resp.ok) {
    const envelope = (body.error ?? body) as {
      code?: string;
      message?: string;
      http_status?: number;
    };
    throw new DatabricksApiError(
      envelope.message || `Request failed with HTTP ${resp.status}`,
      envelope.code,
      resp.status
    );
  }
  return body as T;
}

function normalizeList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) {
    return payload as T[];
  }
  const results = (payload as { results?: unknown } | null | undefined)?.results;
  return Array.isArray(results) ? (results as T[]) : [];
}

// ── Workspaces ────────────────────────────────────────────────────────

export function listWorkspaces(): Promise<DatabricksWorkspace[]> {
  return request<unknown>('/workspaces/').then((data) =>
    normalizeList<DatabricksWorkspace>(data)
  );
}

export function getWorkspace(id: string): Promise<DatabricksWorkspace> {
  return request<DatabricksWorkspace>(`/workspaces/${id}/`);
}

export function createWorkspace(
  payload: DatabricksWorkspaceCreatePayload
): Promise<DatabricksWorkspace> {
  return request<DatabricksWorkspace>('/workspaces/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function testWorkspace(id: string): Promise<DatabricksTestResult> {
  return request<DatabricksTestResult>(`/workspaces/${id}/test/`, {
    method: 'POST',
  });
}

// ── Credentials ───────────────────────────────────────────────────────

export function listCredentials(workspaceId: string): Promise<DatabricksCredential[]> {
  return request<unknown>(`/workspaces/${workspaceId}/credentials/`).then((data) =>
    normalizeList<DatabricksCredential>(data)
  );
}

export function createCredential(
  workspaceId: string,
  payload: DatabricksCredentialCreatePayload
): Promise<DatabricksCredential> {
  return request<DatabricksCredential>(`/workspaces/${workspaceId}/credentials/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function rotateCredential(
  workspaceId: string,
  credentialId: string,
  clientSecret?: string
): Promise<unknown> {
  return request<unknown>(
    `/workspaces/${workspaceId}/credentials/${credentialId}/rotate/`,
    {
      method: 'POST',
      body: JSON.stringify(clientSecret ? { client_secret: clientSecret } : {}),
    }
  );
}