/**
 * UC mirror browse service (openspec add-databricks-control-plane
 * task 1.9) — the client for the 1.3 UC browse endpoints.
 *
 * Wire contract (mirrors databricksService):
 *  - listings are DRF-paginated ({count, ..., results}) — normalized at
 *    this boundary so pages never crash on `map is not a function`,
 *  - errors carry the standardized envelope {"error": {"code", "message"}};
 *    the machine-readable CODE survives on DatabricksApiError so the UI
 *    can render the fail-closed OBO surface (DATABRICKS_OBO_REFRESH_FAILED).
 */
import { apiClient } from '@/shared/api/client';
import type {
  UCCatalog,
  UCExternalLocation,
  UCObjectKind,
  UCSchema,
  UCStorageCredential,
  UCTable,
  UCTableDetail,
} from '@/shared/types/databricks';
import { DatabricksApiError } from './databricksService';

// The service's error class is part of its public surface — consumers
// catch and render it by code without importing the sibling module.
export { DatabricksApiError };

const BASE = '/api/v1/databricks';

async function request<T>(url: string): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    headers: {
      ...apiClient._buildHeaders('GET', `${BASE}${url}`),
    },
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
  const results = (payload as { results?: unknown } | null | undefined)?.results;
  return Array.isArray(results) ? (results as T[]) : [];
}

// ── Workspace-level listings ─────────────────────────────────────────

export function listCatalogs(workspaceId: string): Promise<UCCatalog[]> {
  return request<unknown>(`/workspaces/${workspaceId}/uc/catalogs/`).then((data) =>
    normalizeList<UCCatalog>(data)
  );
}

export function listExternalLocations(workspaceId: string): Promise<UCExternalLocation[]> {
  return request<unknown>(`/workspaces/${workspaceId}/uc/external-locations/`).then((data) =>
    normalizeList<UCExternalLocation>(data)
  );
}

export function listStorageCredentials(workspaceId: string): Promise<UCStorageCredential[]> {
  return request<unknown>(`/workspaces/${workspaceId}/uc/storage-credentials/`).then((data) =>
    normalizeList<UCStorageCredential>(data)
  );
}

// ── Catalog-scoped listings ──────────────────────────────────────────

export function listSchemas(workspaceId: string, catalogId: string): Promise<UCSchema[]> {
  return request<unknown>(
    `/workspaces/${workspaceId}/uc/catalogs/${catalogId}/schemas/`
  ).then((data) => normalizeList<UCSchema>(data));
}

// ── Schema-scoped listings ───────────────────────────────────────────

export function listTables(
  workspaceId: string,
  schemaId: string,
  kind: UCObjectKind = 'tables'
): Promise<UCTable[]> {
  return request<unknown>(
    `/workspaces/${workspaceId}/uc/schemas/${schemaId}/${kind}/`
  ).then((data) => normalizeList<UCTable>(data));
}

// ── Table detail (mirror columns + LIVE effective permissions) ───────

export function getTableDetail(
  workspaceId: string,
  tableId: string
): Promise<UCTableDetail> {
  return request<UCTableDetail>(`/workspaces/${workspaceId}/uc/tables/${tableId}/`);
}