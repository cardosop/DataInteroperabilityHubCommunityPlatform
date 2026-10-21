/**
 * warehouseService tests — wire-contract pin (openspec
 * add-databricks-sql-warehouses task 3.7).
 *
 * The 3.7 endpoints: the list is DRF-paginated (``{count, results}`` —
 * normalized at this boundary), the lifecycle actions POST to
 * ``.../sql-warehouses/{id}/start|stop/`` and answer the row's NEW state
 * (the U5 non-blocking contract), and errors carry the standardized
 * envelope with the machine-readable CODE preserved (so the page can
 * render distinct surfaces per code).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  listWarehouses,
  startWarehouse,
  stopWarehouse,
} from './warehouseService';

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.unstubAllGlobals();
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function stubFetch(body: unknown, init?: Partial<{ ok: boolean; status: number }>) {
  const mock = vi.fn().mockResolvedValue({
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

const ROW = {
  warehouse_id: 'wh-1',
  name: 'analytics',
  state: 'STOPPED',
  serverless: true,
  size: null,
  auto_stop_mins: 30,
};

describe('listWarehouses — pagination normalization', () => {
  it('unwraps the DRF paginated envelope', async () => {
    stubFetch({ count: 2, next: null, previous: null, results: [ROW] });
    const rows = await listWarehouses('ws-1');
    expect(rows).toEqual([ROW]);
  });

  it('targets the nested endpoint', async () => {
    const fetchMock = stubFetch({ count: 0, results: [] });
    await listWarehouses('ws-1');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/sql-warehouses/',
      expect.objectContaining({ method: 'GET' })
    );
  });
});

describe('lifecycle actions', () => {
  it('start POSTs to the start path and returns the new state', async () => {
    const fetchMock = stubFetch({ ...ROW, state: 'STARTING' });
    const row = await startWarehouse('ws-1', 'wh-1');
    expect(row.state).toBe('STARTING');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/sql-warehouses/wh-1/start/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('stop POSTs to the stop path', async () => {
    const fetchMock = stubFetch({ ...ROW, state: 'STOPPING' });
    const row = await stopWarehouse('ws-1', 'wh-1');
    expect(row.state).toBe('STOPPING');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/sql-warehouses/wh-1/stop/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('preserves the machine-readable code on failures', async () => {
    stubFetch(
      { error: { code: 'DATABRICKS_AUTH_FAILED', message: 'Warehouse start failed' } },
      { ok: false, status: 502 }
    );
    await expect(startWarehouse('ws-1', 'wh-1')).rejects.toMatchObject({
      name: 'DatabricksApiError',
      code: 'DATABRICKS_AUTH_FAILED',
    });
  });

  it('preserves the state-error code (409)', async () => {
    stubFetch(
      { code: 'DATABRICKS_WAREHOUSE_STATE_ERROR', message: 'cannot start a DELETING warehouse' },
      { ok: false, status: 409 }
    );
    await expect(startWarehouse('ws-1', 'wh-1')).rejects.toMatchObject({
      code: 'DATABRICKS_WAREHOUSE_STATE_ERROR',
    });
  });
});
