/**
 * Databricks cost-budget API service — openspec
 * add-databricks-cost-guardrails task 7.6.
 *
 * Wire contract (mirrors jobsService):
 *  - the endpoint is DRF-paginated ({count, ..., results}) — normalized
 *    at this boundary so pages never crash on `map is not a function`,
 *  - errors carry the standardized envelope (either {"error": {code,
 *    message}} from the exception handler or the top-level {code,
 *    message} shape); the machine-readable CODE is preserved on
 *    DatabricksApiError so the UI can render distinct surfaces per
 *    code.
 */
import { apiClient } from '@/shared/api/client';
import type { DatabricksCostBudget } from '@/shared/types/databricks';

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
      resp.status
    );
  }
  return body as T;
}

/** The tenant's cost-budget rows with the rolling progress (the U9 page). */
export async function listBudgets(): Promise<DatabricksCostBudget[]> {
  const envelope = await request<{ results?: DatabricksCostBudget[] }>('/budgets/');
  return envelope.results ?? [];
}