/**
 * databricksService tests — wire-contract pin (openspec
 * add-databricks-control-plane task 0.15).
 *
 * The backend (hub/apps/databricks_admin) paginates the workspace list via
 * the DRF global StandardPageNumberPagination (``{count, ..., results}``)
 * and answers errors with the standardized envelope
 * ``{"error": {"code": "...", "message": "..."}}`` (hub/apps/api/exceptions).
 *
 * These tests pin the boundary contract:
 *  - paginated envelope unwraps ``results`` (the warehouseService crash
 *    class — ``workspaces.map is not a function``),
 *  - error extraction surfaces the machine-readable CODE (so the UI can
 *    render the DATABRICKS_CONTROL_PLANE_DISABLED banner) and the human
 *    message (never "[object Object]").
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  createCredential,
  createWorkspace,
  DatabricksApiError,
  listCredentials,
  listWorkspaces,
  rotateCredential,
  testWorkspace,
} from './databricksService';

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.unstubAllGlobals();
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function stubFetch(
  body: unknown,
  init?: Partial<{ ok: boolean; status: number }>
) {
  const mock = vi.fn().mockResolvedValue({
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

describe('listWorkspaces — pagination normalization', () => {
  it('unwraps the DRF paginated envelope', async () => {
    stubFetch({
      count: 2,
      next: null,
      previous: null,
      results: [{ id: 'a', name: 'prod' }],
    });
    const workspaces = await listWorkspaces();
    expect(workspaces).toEqual([{ id: 'a', name: 'prod' }]);
  });

  it('passes a bare array through', async () => {
    stubFetch([{ id: 'b', name: 'dev' }]);
    const workspaces = await listWorkspaces();
    expect(workspaces).toEqual([{ id: 'b', name: 'dev' }]);
  });

  it('degrades unknown shapes to [] instead of crashing', async () => {
    stubFetch({ error: { code: 'X', message: 'drift' } });
    const workspaces = await listWorkspaces();
    expect(workspaces).toEqual([]);
  });
});

describe('error envelope extraction', () => {
  it('surfaces the machine-readable code and human message', async () => {
    stubFetch(
      {
        error: {
          code: 'DATABRICKS_CONTROL_PLANE_DISABLED',
          message: 'Databricks control plane is disabled for this tenant',
          http_status: 403,
        },
      },
      { ok: false, status: 403 }
    );
    await expect(listWorkspaces()).rejects.toMatchObject({
      code: 'DATABRICKS_CONTROL_PLANE_DISABLED',
      message: expect.stringContaining('Databricks control plane is disabled'),
    });
  });

  it('surfaces domain validation codes from field errors', async () => {
    stubFetch(
      {
        error: {
          code: 'DATABRICKS_HOST_NOT_ALLOWED',
          message: "Host 'attacker.example.com' is not a Databricks workspace host.",
          http_status: 400,
        },
      },
      { ok: false, status: 400 }
    );
    await expect(
      createWorkspace({ name: 'x', host: 'attacker.example.com', cloud: 'AWS', region: 'us-east-1' })
    ).rejects.toBeInstanceOf(DatabricksApiError);
    const err = await createWorkspace({
      name: 'x',
      host: 'attacker.example.com',
      cloud: 'AWS',
      region: 'us-east-1',
    }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DatabricksApiError);
    expect((err as DatabricksApiError).code).toBe('DATABRICKS_HOST_NOT_ALLOWED');
  });

  it('falls back to HTTP status when the envelope is missing', async () => {
    stubFetch({}, { ok: false, status: 500 });
    const err = await listWorkspaces().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DatabricksApiError);
    expect((err as DatabricksApiError).message).toContain('500');
  });
});

describe('endpoint wiring', () => {
  it('creates a workspace with POST to /workspaces/', async () => {
    const mock = stubFetch({ id: 'w1', status: 'REGISTERED' });
    await createWorkspace({
      name: 'prod',
      host: 'dbc-x.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
      metastore_id: 'm1',
    });
    expect(mock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/',
      expect.objectContaining({ method: 'POST' })
    );
    const body = JSON.parse(
      (mock.mock.calls[0][1] as RequestInit).body as string
    );
    expect(body).toEqual({
      name: 'prod',
      host: 'dbc-x.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
      metastore_id: 'm1',
    });
  });

  it('tests a workspace with POST to /workspaces/<id>/test/', async () => {
    const mock = stubFetch({ status: 'ok', latency_ms: 12 });
    await testWorkspace('w1');
    expect(mock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/w1/test/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('lists credentials for a workspace', async () => {
    stubFetch([{ id: 'c1', auth_mode: 'PAT' }]);
    const creds = await listCredentials('w1');
    expect(creds).toEqual([{ id: 'c1', auth_mode: 'PAT' }]);
  });

  it('creates a credential with POST to /workspaces/<id>/credentials/', async () => {
    const mock = stubFetch({ id: 'c2', auth_mode: 'PAT' });
    await createCredential('w1', { auth_mode: 'PAT', config: { token: 'dapi-1' } });
    expect(mock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/w1/credentials/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('rotates a credential with POST to the rotate endpoint', async () => {
    const mock = stubFetch({ ok: true });
    await rotateCredential('w1', 'c1');
    expect(mock).toHaveBeenCalledWith(
      '/api/v1/databricks/workspaces/w1/credentials/c1/rotate/',
      expect.objectContaining({ method: 'POST' })
    );
  });
});
