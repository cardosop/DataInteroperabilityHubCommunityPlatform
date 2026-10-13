/**
 * SQL-warehouse lifecycle API service — openspec add-databricks-sql-warehouses
 * task 3.7.
 *
 * Wire contract (mirrors databricksService):
 *  - the list endpoint is DRF-paginated ({count, ..., results}) — normalized
 *    at this boundary so pages never crash on `map is not a function`,
 *  - start/stop POST to `.../sql-warehouses/{id}/start|stop/` and answer
 *    the row's NEW state (the U5 non-blocking contract),
 *  - errors carry the standardized envelope (either {"error": {code,
 *    message}} from the exception handler or the top-level {code, message}
 *    shape the manual 409/502 Responses use); the machine-readable CODE is
 *    preserved on DatabricksApiError so the UI can render distinct
 *    surfaces per code.
 */
import { apiClient } from '@/shared/api/client';
import type { SqlWarehouse } from '@/shared/types/databricks';

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

/** The workspace's mirrored SQL warehouses (DRF pagination unwrapped). */
export async function listWarehouses(workspaceId: string): Promise<SqlWarehouse[]> {
  const payload = await request<{ results: SqlWarehouse[] }>(
    `/workspaces/${workspaceId}/sql-warehouses/`,
  );
  return payload.results ?? [];
}

/** START a warehouse (a no-op at the API when it is already running). */
export async function startWarehouse(
  workspaceId: string,
  warehouseId: string,
): Promise<SqlWarehouse> {
  return request<SqlWarehouse>(
    `/workspaces/${workspaceId}/sql-warehouses/${warehouseId}/start/`,
    { method: 'POST' },
  );
}

/** STOP a warehouse (a no-op at the API when it is already stopped). */
export async function stopWarehouse(
  workspaceId: string,
  warehouseId: string,
): Promise<SqlWarehouse> {
  return request<SqlWarehouse>(
    `/workspaces/${workspaceId}/sql-warehouses/${warehouseId}/stop/`,
    { method: 'POST' },
  );
}