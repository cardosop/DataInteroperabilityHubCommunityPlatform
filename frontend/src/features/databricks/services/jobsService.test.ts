/**
 * jobsService tests — wire-contract pin (openspec add-databricks-jobs
 * task 4.5).
 *
 * The 4.5 endpoints: both lists are DRF-paginated (``{count, results}``
 * — normalized at this boundary), the runs list nests under a job
 * (the Databricks-side string id, not a UUID), and errors carry the
 * standardized envelope with the machine-readable CODE preserved (so
 * the page can render distinct surfaces per code).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { listJobRuns, listJobs } from './jobsService';

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

const JOB = {
  job_id: '12345',
  name: 'nightly-etl',
  task_config: [{ task_key: 'ingest', spark_sql_task: { query: 'SELECT 1' } }],
  schedule: { quartz_cron_expression: '0 0 3 * * ?', timezone_id: 'UTC' },
  synced_at: '2026-09-12T19:00:00Z',
};

const RUN = {
  run_id: '67890',
  lifecycle_state: 'TERMINATED',
  result_state: 'SUCCESS',
  duration_ms: 45000,
  error_message: null,
  synced_at: '2026-09-12T19:05:00Z',
};

describe('listJobs — pagination normalization', () => {
  it('unwraps the DRF paginated envelope', async () => {
    stubFetch({ count: 1, next: null, previous: null, results: [JOB] });
    const rows = await listJobs('ws-1');
    expect(rows).toEqual([JOB]);
  });

  it('targets the nested jobs endpoint', async () => {
    const fetchMock = stubFetch({ count: 0, results: [] });
    await listJobs('ws-1');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/jobs/',
      expect.objectContaining({ method: 'GET' })
    );
  });
});

describe('listJobRuns — the job-nested runs list', () => {
  it('unwraps the DRF paginated envelope', async () => {
    stubFetch({ count: 1, next: null, previous: null, results: [RUN] });
    const rows = await listJobRuns('ws-1', '12345');
    expect(rows).toEqual([RUN]);
  });

  it('targets the job-nested runs endpoint', async () => {
    const fetchMock = stubFetch({ count: 0, results: [] });
    await listJobRuns('ws-1', '12345');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/ws-1/jobs/12345/runs/',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('preserves the machine-readable code on failures', async () => {
    stubFetch(
      { error: { code: 'DATABRICKS_CONTROL_PLANE_DISABLED', message: 'disabled' } },
      { ok: false, status: 403 }
    );
    await expect(listJobRuns('ws-1', '12345')).rejects.toMatchObject({
      name: 'DatabricksApiError',
      code: 'DATABRICKS_CONTROL_PLANE_DISABLED',
    });
  });
});
