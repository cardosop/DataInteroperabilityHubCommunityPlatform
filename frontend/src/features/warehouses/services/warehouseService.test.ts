/**
 * warehouseService tests — response-shape normalization (Phase 1.5).
 *
 * The backend paginates BOTH list endpoints via the DRF global
 * ``StandardPageNumberPagination`` (``hub/settings.py``), so the wire
 * shape is ``{count, ..., results: [...]}`` — proven by
 * ``hub/apps/warehouses/tests/test_views.py`` asserting
 * ``resp.data["results"] == []``. The service declared
 * ``Promise<WarehouseConnection[]>`` and returned the raw payload, so
 * ``ConnectionListPage`` set the whole envelope into state and crashed
 * with ``connections.map is not a function`` on EVERY render whenever
 * the feature flag was enabled — the ``tenants.find`` crash class.
 *
 * These tests pin the normalization AT THE SERVICE BOUNDARY:
 * bare array passes through; the paginated envelope unwraps ``results``;
 * any other shape (error envelope, drift) degrades to ``[]``.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  listACLs,
  listConnections,
} from './warehouseService';

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.unstubAllGlobals();
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function stubFetch(json: unknown, init?: Partial<{ ok: boolean }>) {
  const mock = vi.fn().mockResolvedValue({
    ok: init?.ok ?? true,
    json: () => Promise.resolve(json),
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

describe('listConnections — service-boundary normalization', () => {
  it('returns a bare array unchanged', async () => {
    const connections = [{ id: 'c1', name: 'Warehouse One' }];
    const fetchMock = stubFetch(connections);

    const result = await listConnections();

    expect(result).toEqual(connections);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/warehouses/connections/',
      expect.anything(),
    );
  });

  it('unwraps the REAL paginated backend envelope', async () => {
    const connections = [{ id: 'c1', name: 'Warehouse One' }];
    stubFetch({ count: 1, results: connections, next: null, previous: null });

    const result = await listConnections();

    expect(result).toEqual(connections);
  });

  it('degrades a non-array payload to []', async () => {
    stubFetch({ error: 'proxy exploded', detail: 'boom' });

    expect(await listConnections()).toEqual([]);
  });

  it('degrades a null payload to []', async () => {
    stubFetch(null);

    expect(await listConnections()).toEqual([]);
  });
});

describe('listACLs — service-boundary normalization', () => {
  it('unwraps the paginated envelope (same backend default)', async () => {
    const acls = [{ id: 'a1', connection: 'c1', user: 'u1', role: 'viewer' }];
    stubFetch({ count: 1, results: acls });

    expect(await listACLs()).toEqual(acls);
  });

  it('returns a bare array unchanged', async () => {
    const acls = [{ id: 'a1', connection: 'c1', user: 'u1', role: 'viewer' }];
    stubFetch(acls);

    expect(await listACLs()).toEqual(acls);
  });

  it('degrades a non-array payload to []', async () => {
    stubFetch({ detail: 'not found' });

    expect(await listACLs()).toEqual([]);
  });
});
