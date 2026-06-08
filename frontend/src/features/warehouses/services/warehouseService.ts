/**
 * Warehouse API Service — Phase 275
 *
 * Client for /api/v1/warehouses/connections/, /acls/, and /share/ endpoints.
 */
import type {
  DeltaShareTable,
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

// ── Connections ──────────────────────────────────────────────────────

export function listConnections(): Promise<WarehouseConnection[]> {
  return request<WarehouseConnection[]>('/connections/');
}

export function getConnection(id: string): Promise<WarehouseConnection> {
  return request<WarehouseConnection>(`/connections/${id}/`);
}

export function createConnection(
  payload: WarehouseConnectionCreatePayload,
): Promise<WarehouseConnection> {
  return request<WarehouseConnection>('/connections/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateConnection(
  id: string,
  payload: Partial<WarehouseConnectionCreatePayload>,
): Promise<WarehouseConnection> {
  return request<WarehouseConnection>(`/connections/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteConnection(id: string): Promise<void> {
  return request<void>(`/connections/${id}/`, { method: 'DELETE' });
}

export function testConnection(
  id: string,
): Promise<WarehouseConnectionTestResult> {
  return request<WarehouseConnectionTestResult>(`/connections/${id}/test/`, {
    method: 'POST',
  });
}

export function reflectSchema(
  id: string,
  table: string,
): Promise<SchemaReflection> {
  return request<SchemaReflection>(
    `/connections/${id}/schema/?table=${encodeURIComponent(table)}`,
  );
}

export function listResidencyMismatches(): Promise<{
  count: number;
  mismatches: ResidencyMismatch[];
}> {
  return request('/connections/residency-mismatches/');
}

// ── ACLs ─────────────────────────────────────────────────────────────

export function listACLs(): Promise<WarehouseConnectionACL[]> {
  return request<WarehouseConnectionACL[]>('/acls/');
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

// ── Delta Sharing ────────────────────────────────────────────────────

export function listShareTables(assetId: string): Promise<{
  share: { name: string };
  tables: DeltaShareTable[];
}> {
  return request(`/share/${assetId}/`);
}

export function queryShareTable(
  assetId: string,
  limit = 100,
): Promise<{ rows: unknown[][] }> {
  return request(`/share/${assetId}/query/?limit=${limit}`);
}
