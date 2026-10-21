/**
 * ML-assets management API service — openspec
 * add-databricks-ml-assets task 12.6.
 *
 * Wire contract (mirrors dltService/jobsService):
 *  - the list endpoints are DRF-paginated ({count, ..., results}) —
 *    normalized at this boundary,
 *  - the model id rides the PATH (the mirror row's UUID); the serving
 *    endpoint name rides the PATH (the Databricks-side string name),
 *  - errors carry the standardized envelope ({"error": {code,
 *    message}}); the machine-readable CODE is preserved on
 *    DatabricksApiError so the UI can render distinct surfaces per
 *    code (the flag-off 403 banner, the classified 404).
 */
import { apiClient } from '@/shared/api/client';
import type {
  DatabricksMlServingEndpoint,
  UCModelSummary,
  UCTable,
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
    method: init?.method ?? 'GET',
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
      resp.status,
    );
  }
  return body as T;
}

async function list<T>(path: string): Promise<T[]> {
  const payload = await request<{ results: T[] }>(path);
  return payload.results ?? [];
}

/** The workspace's mirrored registered models (mirror-first list). */
export async function listMlModels(workspaceId: string): Promise<UCModelSummary[]> {
  return list<UCModelSummary>(`/workspaces/${workspaceId}/ml-assets/models/`);
}

/**
 * Register a model through the UC REST surface — the payload carries
 * the three-part `catalog.schema.name` full name; a malformed name
 * refuses 400 DATABRICKS_ML_INVALID_FULL_NAME.
 */
export async function registerMlModel(
  workspaceId: string,
  fullName: string,
): Promise<{ id: string; name: string; full_name: string }> {
  return request(`/workspaces/${workspaceId}/ml-assets/models/`, {
    method: 'POST',
    body: JSON.stringify({ full_name: fullName }),
  });
}

/** Log a model version through the MLflow surface (the 12.2 service). */
export async function logMlModelVersion(
  workspaceId: string,
  modelId: string,
  body: { source: string; run_id?: string },
): Promise<{ version: number }> {
  return request(`/workspaces/${workspaceId}/ml-assets/models/${modelId}/versions/`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Set (or re-point) a model alias through the UC REST surface. */
export async function setMlModelAlias(
  workspaceId: string,
  modelId: string,
  alias: string,
  versionNum: number,
): Promise<unknown> {
  return request(
    `/workspaces/${workspaceId}/ml-assets/models/${modelId}/aliases/${encodeURIComponent(alias)}/`,
    {
      method: 'PUT',
      body: JSON.stringify({ version_num: versionNum }),
    },
  );
}

/** Remove a model alias through the UC REST surface. */
export async function removeMlModelAlias(
  workspaceId: string,
  modelId: string,
  alias: string,
): Promise<void> {
  await request(
    `/workspaces/${workspaceId}/ml-assets/models/${modelId}/aliases/${encodeURIComponent(alias)}/`,
    { method: 'DELETE' },
  );
}

/** The workspace's feature tables (the mirror-derived 12.3 listing). */
export async function listFeatureTables(workspaceId: string): Promise<UCTable[]> {
  return list<UCTable>(`/workspaces/${workspaceId}/ml-assets/feature-tables/`);
}

/** Mark a UC table with the feature_store tag convention. */
export async function markFeatureTable(workspaceId: string, tableId: string): Promise<unknown> {
  return request(`/workspaces/${workspaceId}/ml-assets/tables/${tableId}/feature-tag/`, {
    method: 'POST',
    body: '{}',
  });
}

/** Remove the feature_store tag (idempotent — 404 is the goal state). */
export async function unmarkFeatureTable(workspaceId: string, tableId: string): Promise<void> {
  await request(`/workspaces/${workspaceId}/ml-assets/tables/${tableId}/feature-tag/`, {
    method: 'DELETE',
  });
}

/** The workspace's mirrored serving endpoints (mirror-first list). */
export async function listServingEndpoints(
  workspaceId: string,
): Promise<DatabricksMlServingEndpoint[]> {
  return list<DatabricksMlServingEndpoint>(
    `/workspaces/${workspaceId}/ml-assets/serving-endpoints/`,
  );
}

/** Create a serving endpoint through the pinned client (12.4). */
export async function createServingEndpoint(
  workspaceId: string,
  body: { name: string; config: Record<string, unknown> },
): Promise<DatabricksMlServingEndpoint> {
  return request(`/workspaces/${workspaceId}/ml-assets/serving-endpoints/`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Delete a serving endpoint by name. */
export async function deleteServingEndpoint(
  workspaceId: string,
  name: string,
): Promise<void> {
  await request(
    `/workspaces/${workspaceId}/ml-assets/serving-endpoints/${encodeURIComponent(name)}/`,
    { method: 'DELETE' },
  );
}

/** The workspace's mirrored Vector Search endpoints (mirror-first). */
export async function listVectorSearchEndpoints(
  workspaceId: string,
): Promise<DatabricksMlServingEndpoint[]> {
  return list<DatabricksMlServingEndpoint>(
    `/workspaces/${workspaceId}/ml-assets/vector-search-endpoints/`,
  );
}

/** Create a Vector Search endpoint through the pinned client (12.4). */
export async function createVectorSearchEndpoint(
  workspaceId: string,
  body: { name: string; config: Record<string, unknown> },
): Promise<DatabricksMlServingEndpoint> {
  return request(`/workspaces/${workspaceId}/ml-assets/vector-search-endpoints/`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}