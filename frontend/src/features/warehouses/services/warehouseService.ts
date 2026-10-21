/**
 * Warehouse API Service — Phase 275
 *
 * Client for /api/v1/warehouses/connections/ and /acls/ endpoints.
 *
 * (The fabricated Delta Sharing /share/ client was removed with 5.5 —
 * the native bearer-token protocol surface has no session consumer.)
 */
import type {
  ResidencyMismatch,
  SchemaReflection,
  WarehouseConnection,
  WarehouseConnectionACL,
  WarehouseConnectionCreatePayload,
  WarehouseConnectionTestResult,
} from '@/shared/types/warehouses';

const BASE = '/api/v1/warehouses';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error || `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

/**
 * Normalize a list response at the service boundary (Phase 1.5).
 *
 * The backend paginates both list endpoints via the DRF global
 * ``StandardPageNumberPagination``, so the wire shape is
 * ``{count, ..., results: [...]}`` — not a bare array. Before this
 * normalization ``ConnectionListPage`` set the whole envelope into state
 * and crashed with ``connections.map is not a function`` on every render.
 * Accepts a bare array for forward-compat; anything else degrades to ``[]``
 * so a drift/error shape renders the empty state instead of crashing.
 */
function normalizeList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) {
    return payload as T[];
  }
  const results = (payload as { results?: unknown } | null | undefined)?.results;
  return Array.isArray(results) ? (results as T[]) : [];
}

// ── Connections ──────────────────────────────────────────────────────

export function listConnections(): Promise<WarehouseConnection[]> {
  return request<unknown>('/connections/').then((data) => normalizeList<WarehouseConnection>(data));
}

export function getConnection(id: string): Promise<WarehouseConnection> {
  return request<WarehouseConnection>(`/connections/${id}/`);
}

export function createConnection(
  payload: WarehouseConnectionCreatePayload
): Promise<WarehouseConnection> {
  return request<WarehouseConnection>('/connections/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateConnection(
  id: string,
  payload: Partial<WarehouseConnectionCreatePayload>
): Promise<WarehouseConnection> {
  return request<WarehouseConnection>(`/connections/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteConnection(id: string): Promise<void> {
  return request<void>(`/connections/${id}/`, { method: 'DELETE' });
}

export function testConnection(id: string): Promise<WarehouseConnectionTestResult> {
  return request<WarehouseConnectionTestResult>(`/connections/${id}/test/`, {
    method: 'POST',
  });
}

export function reflectSchema(id: string, table: string): Promise<SchemaReflection> {
  return request<SchemaReflection>(`/connections/${id}/schema/?table=${encodeURIComponent(table)}`);
}

export function listResidencyMismatches(): Promise<{
  count: number;
  mismatches: ResidencyMismatch[];
}> {
  return request('/connections/residency-mismatches/');
}

// ── ACLs ─────────────────────────────────────────────────────────────

export function listACLs(): Promise<WarehouseConnectionACL[]> {
  return request<unknown>('/acls/').then((data) => normalizeList<WarehouseConnectionACL>(data));
}

export function createACL(payload: {
  connection: string;
  user: string;
  role: string;
}): Promise<WarehouseConnectionACL> {
  return request<WarehouseConnectionACL>('/acls/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteACL(id: string): Promise<void> {
  return request<void>(`/acls/${id}/`, { method: 'DELETE' });
}
