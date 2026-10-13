/**
 * budgetService tests — wire-contract pin (openspec
 * add-databricks-cost-guardrails task 7.6).
 *
 * The 7.6 endpoint: DRF-paginated (``{count, results}`` — normalized at
 * this boundary), and errors carry the standardized envelope with the
 * machine-readable CODE preserved (so the page can render distinct
 * surfaces per code).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { listBudgets } from './budgetService';

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
  id: 'budget-1',
  warehouse_id: null,
  warehouse_name: null,
  budget_units_per_hour: '100.000000',
  enforcement_mode: 'BLOCK',
  consumed: '60',
  ratio: 0.6,
  percent: 60.0,
  window_seconds: 3600,
  breakdown: [],
};

describe('listBudgets — the U9 budget page wire', () => {
  it('targets the budgets endpoint', async () => {
    const fetchMock = stubFetch({ count: 1, next: null, previous: null, results: [ROW] });
    await listBudgets();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/budgets/',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('unwraps the DRF paginated envelope', async () => {
    stubFetch({ count: 1, next: null, previous: null, results: [ROW] });
    const rows = await listBudgets();
    expect(rows).toEqual([ROW]);
  });

  it('preserves the machine-readable CODE on errors', async () => {
    stubFetch(
      { error: { code: 'DATABRICKS_CONTROL_PLANE_DISABLED', message: 'nope' } },
      { ok: false, status: 403 }
    );
    await expect(listBudgets()).rejects.toMatchObject({
      code: 'DATABRICKS_CONTROL_PLANE_DISABLED',
    });
  });
});
