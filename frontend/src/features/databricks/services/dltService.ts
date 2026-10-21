/**
 * DLT pipeline management API service — openspec
 * add-databricks-dlt-pipelines task 10.7.
 *
 * Wire contract (mirrors jobsService):
 *  - the list endpoint is DRF-paginated ({count, ..., results}) —
 *    normalized at this boundary,
 *  - the pipeline id rides the PATH (the Databricks-side string id),
 *  - errors carry the standardized envelope ({"error": {code,
 *    message}}); the machine-readable CODE is preserved on
 *    DatabricksApiError so the UI can render distinct surfaces per
 *    code (the flag-off 403 banner, the 409 conflict).
 */
import { apiClient } from '@/shared/api/client';
import type { DatabricksDltPipeline } from '@/shared/types/databricks';

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

/** The workspace's mirrored DLT pipelines (DRF pagination unwrapped). */
export async function listDltPipelines(workspaceId: string): Promise<DatabricksDltPipeline[]> {
  const payload = await request<{ results: DatabricksDltPipeline[] }>(
    `/workspaces/${workspaceId}/dlt-pipelines/`,
  );
  return payload.results ?? [];
}

/**
 * Start an update — the refresh semantics ship exactly as given (the
 * API's documented {tables, files} selection object or a full refresh).
 * A 409 DATABRICKS_DLT_UPDATE_CONFLICT surfaces through the code.
 */
export async function startDltUpdate(
  workspaceId: string,
  pipelineId: string,
  body: { full_refresh: boolean; refresh_selection?: { tables?: string[]; files?: string[] } },
): Promise<{ update_id: string }> {
  return request(`/workspaces/${workspaceId}/dlt-pipelines/${pipelineId}/start/`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Stop the pipeline's active update (a no-op when idle). */
export async function stopDltPipeline(
  workspaceId: string,
  pipelineId: string,
): Promise<{ stopped: boolean; reason?: string }> {
  return request(`/workspaces/${workspaceId}/dlt-pipelines/${pipelineId}/stop/`, {
    method: 'POST',
    body: '{}',
  });
}