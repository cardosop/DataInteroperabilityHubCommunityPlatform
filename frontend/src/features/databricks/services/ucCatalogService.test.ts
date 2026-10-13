/**
 * Pins for ucCatalogService (openspec add-databricks-control-plane task 1.9)
 * — the client for the 1.3 UC browse endpoints.
 *
 * Wire contract (mirrors databricksService):
 *  - listings are DRF-paginated and normalized at this boundary,
 *  - errors carry the standardized envelope; the machine-readable CODE
 *    survives on the thrown DatabricksApiError (the UI renders the
 *    fail-closed OBO code from it).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  listCatalogs,
  listExternalLocations,
  listSchemas,
  listStorageCredentials,
  listTables,
  getTableDetail,
  DatabricksApiError,
} from './ucCatalogService';

const fetchMock = vi.fn();

vi.stubGlobal('fetch', fetchMock);

afterEach(() => {
  fetchMock.mockReset();
});

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

describe('ucCatalogService listings', () => {
  it('listCatalogs normalizes the paginated envelope and hits the 1.3 path', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        count: 2,
        results: [
          { id: 'c1', name: 'main', catalog_type: 'MANAGED', full_name: 'main' },
          { id: 'c2', name: 'analytics', catalog_type: 'MANAGED', full_name: 'analytics' },
        ],
      })
    );
    const catalogs = await listCatalogs('ws-1');
    expect(catalogs.map((c) => c.name)).toEqual(['main', 'analytics']);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/uc/catalogs/',
      expect.any(Object)
    );
  });

  it('listSchemas scopes under the catalog', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ count: 1, results: [{ id: 's1', name: 'sales', full_name: 'main.sales' }] })
    );
    const schemas = await listSchemas('ws-1', 'c1');
    expect(schemas[0].name).toBe('sales');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/uc/catalogs/c1/schemas/',
      expect.any(Object)
    );
  });

  it('listTables scopes under the schema (and every schema-scoped kind resolves)', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ count: 1, results: [{ id: 't1', name: 'orders', full_name: 'main.sales.orders' }] })
    );
    for (const kind of ['tables', 'views', 'volumes', 'models'] as const) {
      const rows = await listTables('ws-1', 's1', kind);
      expect(rows[0].name).toBe('orders');
      expect(fetchMock).toHaveBeenLastCalledWith(
        `/api/v1/databricks/workspaces/ws-1/uc/schemas/s1/${kind}/`,
        expect.any(Object)
      );
    }
  });

  it('workspace-level surfaces resolve their paths', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ count: 0, results: [] }));
    await listExternalLocations('ws-1');
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/v1/databricks/workspaces/ws-1/uc/external-locations/',
      expect.any(Object)
    );
    await listStorageCredentials('ws-1');
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/v1/databricks/workspaces/ws-1/uc/storage-credentials/',
      expect.any(Object)
    );
  });

  it('an empty results list stays an array (no map-crash)', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ count: 0, results: [] }));
    await expect(listCatalogs('ws-1')).resolves.toEqual([]);
  });
});

describe('ucCatalogService table detail', () => {
  it('returns columns + the live effective_permissions payload', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: 't1',
        name: 'orders',
        columns: [{ name: 'id', type_text: 'BIGINT' }],
        full_name: 'main.sales.orders',
        synced_at: '2026-09-10T00:00:00Z',
        effective_permissions: {
          privilege_assignments: [{ principal: 'user-a', privileges: ['SELECT'] }],
        },
      })
    );
    const detail = await getTableDetail('ws-1', 't1');
    expect(detail.columns).toEqual([{ name: 'id', type_text: 'BIGINT' }]);
    expect(detail.effective_permissions?.privilege_assignments[0].principal).toBe('user-a');
  });

  it('preserves the fail-closed OBO code from the error envelope', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          error: {
            code: 'DATABRICKS_OBO_REFRESH_FAILED',
            message: 'sign in with Databricks',
            http_status: 502,
          },
        },
        false,
        502
      )
    );
    const err = await getTableDetail('ws-1', 't1').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DatabricksApiError);
    expect((err as DatabricksApiError).code).toBe('DATABRICKS_OBO_REFRESH_FAILED');
    expect((err as DatabricksApiError).httpStatus).toBe(502);
  });
});
