/**
 * mlAssetsService tests — wire-contract pins (openspec
 * add-databricks-ml-assets task 12.6).
 *
 * The 12.6 endpoints: both lists are DRF-paginated (``{count, results}``
 * — normalized at this boundary), the model id rides the PATH (the
 * mirror row's UUID), the serving endpoint name rides the PATH (the
 * Databricks-side string name), and errors carry the standardized
 * envelope with the machine-readable CODE preserved (so the page can
 * render distinct surfaces per code — the flag-off 403 banner, the
 * classified 404).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  createServingEndpoint,
  createVectorSearchEndpoint,
  deleteServingEndpoint,
  listFeatureTables,
  listMlModels,
  listServingEndpoints,
  listVectorSearchEndpoints,
  logMlModelVersion,
  markFeatureTable,
  registerMlModel,
  removeMlModelAlias,
  setMlModelAlias,
  unmarkFeatureTable,
} from './mlAssetsService';

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

const MODEL = {
  id: 'm-1',
  name: 'churn_model',
  full_name: 'ml_catalog.ml_schema.churn_model',
  comment: '',
  owner: '',
  aliases: [],
  latest_version: 0,
  synced_at: '2026-09-15T12:00:00Z',
};

const TABLE = {
  id: 't-1',
  name: 'churn_features',
  full_name: 'ml_catalog.ml_schema.churn_features',
  table_type: 'MANAGED',
  tags: [{ key: 'feature_store', value: 'true' }],
  synced_at: '2026-09-15T12:00:00Z',
};

const ENDPOINT = {
  id: 'ep-1',
  name: 'ep-1',
  endpoint_type: 'SERVING',
  state: 'READY',
  config: {},
  synced_at: '2026-09-15T12:00:00Z',
};

const BASE = '/api/v1/databricks/workspaces/ws-1/ml-assets';

describe('listMlModels — pagination normalization', () => {
  it('unwraps the DRF paginated envelope', async () => {
    stubFetch({ count: 1, results: [MODEL] });
    expect(await listMlModels('ws-1')).toEqual([MODEL]);
  });

  it('targets the models endpoint', async () => {
    const fetchMock = stubFetch({ count: 0, results: [] });
    await listMlModels('ws-1');
    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/models/`, expect.anything());
  });
});

describe('registerMlModel — the register wire contract', () => {
  it('POSTs the full_name to the models endpoint', async () => {
    const fetchMock = stubFetch({ id: 'm-1', name: 'churn_model', full_name: MODEL.full_name });
    await registerMlModel('ws-1', MODEL.full_name);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/models/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ full_name: MODEL.full_name });
  });
});

describe('logMlModelVersion — the version-log wire contract', () => {
  it('POSTs source and run_id to the versions path', async () => {
    const fetchMock = stubFetch({ version: 7 });
    await logMlModelVersion('ws-1', 'm-1', { source: 'dbfs:/ml/churn', run_id: 'run-abc' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/models/m-1/versions/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ source: 'dbfs:/ml/churn', run_id: 'run-abc' });
  });
});

describe('alias operations — the UC REST wire contract', () => {
  it('setMlModelAlias PUTs version_num to the alias path', async () => {
    const fetchMock = stubFetch({});
    await setMlModelAlias('ws-1', 'm-1', 'champion', 7);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/models/m-1/aliases/champion/`);
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({ version_num: 7 });
  });

  it('removeMlModelAlias DELETEs the alias path', async () => {
    const fetchMock = stubFetch({}, { ok: true });
    await removeMlModelAlias('ws-1', 'm-1', 'champion');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/models/m-1/aliases/champion/`);
    expect(init.method).toBe('DELETE');
  });
});

describe('feature tables — the tag convention wire contract', () => {
  it('listFeatureTables unwraps the paginated envelope', async () => {
    stubFetch({ count: 1, results: [TABLE] });
    expect(await listFeatureTables('ws-1')).toEqual([TABLE]);
  });

  it('markFeatureTable POSTs to the feature-tag path', async () => {
    const fetchMock = stubFetch({});
    await markFeatureTable('ws-1', 't-1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/tables/t-1/feature-tag/`);
    expect(init.method).toBe('POST');
  });

  it('unmarkFeatureTable DELETEs the feature-tag path', async () => {
    const fetchMock = stubFetch({}, { ok: true });
    await unmarkFeatureTable('ws-1', 't-1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/tables/t-1/feature-tag/`);
    expect(init.method).toBe('DELETE');
  });
});

describe('serving endpoints — the 12.4 surface wire contract', () => {
  it('listServingEndpoints unwraps the paginated envelope', async () => {
    stubFetch({ count: 1, results: [ENDPOINT] });
    expect(await listServingEndpoints('ws-1')).toEqual([ENDPOINT]);
  });

  it('createServingEndpoint POSTs name and config', async () => {
    const fetchMock = stubFetch(ENDPOINT);
    await createServingEndpoint('ws-1', { name: 'ep-1', config: { served_models: [] } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/serving-endpoints/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ name: 'ep-1', config: { served_models: [] } });
  });

  it('deleteServingEndpoint DELETEs the name path', async () => {
    const fetchMock = stubFetch({}, { ok: true });
    await deleteServingEndpoint('ws-1', 'ep-1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/serving-endpoints/ep-1/`);
    expect(init.method).toBe('DELETE');
  });

  it('listVectorSearchEndpoints reads the vector surface', async () => {
    const fetchMock = stubFetch({ count: 1, results: [{ ...ENDPOINT, endpoint_type: 'VECTOR' }] });
    await listVectorSearchEndpoints('ws-1');
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/vector-search-endpoints/`);
  });

  it('createVectorSearchEndpoint POSTs to the vector surface', async () => {
    const fetchMock = stubFetch({ ...ENDPOINT, endpoint_type: 'VECTOR' });
    await createVectorSearchEndpoint('ws-1', { name: 'vep-1', config: {} });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/vector-search-endpoints/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ name: 'vep-1', config: {} });
  });
});

describe('the error envelope — the machine-readable code survives', () => {
  it('surfaces the flag-off 403 code', async () => {
    stubFetch(
      { error: { code: 'DATABRICKS_ML_ASSETS_DISABLED', message: 'disabled' } },
      { ok: false, status: 403 },
    );
    await expect(listMlModels('ws-1')).rejects.toMatchObject({
      code: 'DATABRICKS_ML_ASSETS_DISABLED',
      httpStatus: 403,
    });
  });
});
