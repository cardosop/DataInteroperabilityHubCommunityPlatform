/**
 * Vitest pins for the ML-assets page (openspec add-databricks-ml-assets
 * task 12.6).
 *
 * The service module is the sanctioned seam (the repo's frontend
 * convention — the page logic itself is real): the pins assert the
 * rendered mirror states, the flag-off banner, the machine-readable
 * error surface, and that register/version-log/alias/tag/serving
 * actions call the service with the exact args the views expect.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DatabricksMlServingEndpoint, UCModelSummary } from '@/shared/types/databricks';

import { MlAssetsPage } from './MlAssetsPage';

import {
  DatabricksApiError,
  createServingEndpoint,
  createVectorSearchEndpoint,
  deleteServingEndpoint,
  listFeatureTables,
  listMlModels,
  listServingEndpoints,
  listVectorSearchEndpoints,
  logMlModelVersion,
  registerMlModel,
  removeMlModelAlias,
  setMlModelAlias,
  unmarkFeatureTable,
} from '../services/mlAssetsService';

vi.mock('../services/mlAssetsService', () => {
  class MockError extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.name = 'DatabricksApiError';
      this.code = code;
    }
  }
  return {
    DatabricksApiError: MockError,
    listMlModels: vi.fn(),
    registerMlModel: vi.fn(),
    logMlModelVersion: vi.fn(),
    setMlModelAlias: vi.fn(),
    removeMlModelAlias: vi.fn(),
    listFeatureTables: vi.fn(),
    markFeatureTable: vi.fn(),
    unmarkFeatureTable: vi.fn(),
    listServingEndpoints: vi.fn(),
    createServingEndpoint: vi.fn(),
    deleteServingEndpoint: vi.fn(),
    listVectorSearchEndpoints: vi.fn(),
    createVectorSearchEndpoint: vi.fn(),
  };
});

const MODEL: UCModelSummary = {
  id: 'm-1',
  name: 'churn_model',
  full_name: 'ml_catalog.ml_schema.churn_model',
  comment: '',
  owner: '',
  aliases: [{ alias_name: 'champion', version_num: 3 }],
  latest_version: 3,
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

const ENDPOINT: DatabricksMlServingEndpoint = {
  id: 'ep-1',
  name: 'ep-1',
  endpoint_type: 'SERVING',
  state: 'READY',
  config: {},
  synced_at: '2026-09-15T12:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/databricks/workspaces/ws-1/ml-assets']}>
      <Routes>
        <Route path="/databricks/workspaces/:workspaceId/ml-assets" element={<MlAssetsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(listMlModels).mockResolvedValue([MODEL]);
  vi.mocked(listFeatureTables).mockResolvedValue([TABLE]);
  vi.mocked(listServingEndpoints).mockResolvedValue([ENDPOINT]);
  vi.mocked(listVectorSearchEndpoints).mockResolvedValue([]);
  vi.mocked(registerMlModel).mockResolvedValue({ id: 'm-1', name: 'churn_model' });
  vi.mocked(logMlModelVersion).mockResolvedValue({ version: 4 });
  vi.mocked(setMlModelAlias).mockResolvedValue({});
  vi.mocked(removeMlModelAlias).mockResolvedValue();
  vi.mocked(unmarkFeatureTable).mockResolvedValue();
  vi.mocked(createServingEndpoint).mockResolvedValue(ENDPOINT);
  vi.mocked(deleteServingEndpoint).mockResolvedValue();
  vi.mocked(createVectorSearchEndpoint).mockResolvedValue({
    ...ENDPOINT,
    endpoint_type: 'VECTOR',
  });
  vi.clearAllMocks();
});

describe('the mirror states render', () => {
  it('renders the mirrored models with the reported aliases', async () => {
    renderPage();
    expect(await screen.findByText('churn_model')).toBeTruthy();
    expect(screen.getByTestId('ml-model-full-name-m-1').textContent).toContain(
      'ml_catalog.ml_schema.churn_model',
    );
    expect(screen.getByTestId('ml-model-aliases-m-1').textContent).toContain('champion');
  });

  it('renders the feature tables with the tag identity', async () => {
    renderPage();
    expect(await screen.findByTestId('ml-feature-tables-table')).toBeTruthy();
    expect(screen.getByText('churn_features')).toBeTruthy();
  });

  it('renders the serving endpoints with the reported state', async () => {
    renderPage();
    expect(await screen.findByTestId('ml-serving-table')).toBeTruthy();
    expect(screen.getByText('ep-1')).toBeTruthy();
    expect(screen.getByText('READY')).toBeTruthy();
  });
});

describe('the flag-off and error surfaces', () => {
  it('renders the flag-off banner on the 403 code', async () => {
    vi.mocked(listMlModels).mockRejectedValue(
      new DatabricksApiError('disabled', 'DATABRICKS_ML_ASSETS_DISABLED'),
    );
    renderPage();
    expect(await screen.findByTestId('ml-assets-flag-banner')).toBeTruthy();
  });

  it('renders the machine-readable code on other failures', async () => {
    vi.mocked(listMlModels).mockRejectedValue(
      new DatabricksApiError('boom', 'DATABRICKS_UC_OBJECT_NOT_FOUND'),
    );
    renderPage();
    const error = await screen.findByTestId('ml-assets-error');
    expect(error.textContent).toContain('DATABRICKS_UC_OBJECT_NOT_FOUND');
  });
});

describe('the operations call the service with the exact args', () => {
  it('registers a model with the full name', async () => {
    renderPage();
    await screen.findByTestId('ml-models-table');
    fireEvent.change(screen.getByTestId('ml-register-input'), {
      target: { value: 'ml_catalog.ml_schema.next_model' },
    });
    fireEvent.click(screen.getByTestId('ml-register-button'));
    expect(registerMlModel).toHaveBeenCalledWith('ws-1', 'ml_catalog.ml_schema.next_model');
  });

  it('logs a version with source and run id', async () => {
    renderPage();
    await screen.findByTestId('ml-models-table');
    fireEvent.change(screen.getByTestId('ml-version-source-m-1'), {
      target: { value: 'dbfs:/ml/churn' },
    });
    fireEvent.click(screen.getByTestId('ml-version-log-m-1'));
    expect(logMlModelVersion).toHaveBeenCalledWith('ws-1', 'm-1', {
      source: 'dbfs:/ml/churn',
    });
  });

  it('sets an alias with the version number', async () => {
    renderPage();
    await screen.findByTestId('ml-models-table');
    fireEvent.change(screen.getByTestId('ml-alias-input-m-1'), {
      target: { value: 'challenger' },
    });
    fireEvent.change(screen.getByTestId('ml-alias-version-input-m-1'), {
      target: { value: '4' },
    });
    fireEvent.click(screen.getByTestId('ml-alias-set-m-1'));
    expect(setMlModelAlias).toHaveBeenCalledWith('ws-1', 'm-1', 'challenger', 4);
  });

  it('removes an alias', async () => {
    renderPage();
    await screen.findByTestId('ml-models-table');
    fireEvent.click(screen.getByTestId('ml-alias-remove-m-1-champion'));
    expect(removeMlModelAlias).toHaveBeenCalledWith('ws-1', 'm-1', 'champion');
  });

  it('marks and unmarks a feature table', async () => {
    renderPage();
    await screen.findByTestId('ml-feature-tables-table');
    fireEvent.click(screen.getByTestId('ml-feature-unmark-t-1'));
    expect(unmarkFeatureTable).toHaveBeenCalledWith('ws-1', 't-1');
  });

  it('creates a serving endpoint with the parsed config', async () => {
    renderPage();
    await screen.findByTestId('ml-serving-table');
    fireEvent.change(screen.getByTestId('ml-serving-name-input'), {
      target: { value: 'ep-2' },
    });
    fireEvent.change(screen.getByTestId('ml-serving-config-input'), {
      target: { value: '{"served_models": [{"name": "churn_model"}]}' },
    });
    fireEvent.click(screen.getByTestId('ml-serving-create'));
    expect(createServingEndpoint).toHaveBeenCalledWith('ws-1', {
      name: 'ep-2',
      config: { served_models: [{ name: 'churn_model' }] },
    });
  });

  it('deletes a serving endpoint by name', async () => {
    renderPage();
    await screen.findByTestId('ml-serving-table');
    fireEvent.click(screen.getByTestId('ml-serving-delete-ep-1'));
    expect(deleteServingEndpoint).toHaveBeenCalledWith('ws-1', 'ep-1');
  });

  it('creates a vector search endpoint on the vector surface', async () => {
    renderPage();
    await screen.findByTestId('ml-vector-table');
    fireEvent.change(screen.getByTestId('ml-vector-name-input'), {
      target: { value: 'vep-1' },
    });
    fireEvent.click(screen.getByTestId('ml-vector-create'));
    expect(createVectorSearchEndpoint).toHaveBeenCalledWith('ws-1', { name: 'vep-1', config: {} });
  });

  it('surfaces a config parse failure without calling the service', async () => {
    renderPage();
    await screen.findByTestId('ml-serving-table');
    fireEvent.change(screen.getByTestId('ml-serving-name-input'), {
      target: { value: 'ep-2' },
    });
    fireEvent.change(screen.getByTestId('ml-serving-config-input'), {
      target: { value: '{not json' },
    });
    fireEvent.click(screen.getByTestId('ml-serving-create'));
    expect(createServingEndpoint).not.toHaveBeenCalled();
    expect(await screen.findByTestId('ml-assets-action-error')).toBeTruthy();
  });
});
