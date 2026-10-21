/**
 * ML-assets management page (openspec add-databricks-ml-assets task
 * 12.6) — the DS management surface for the flag-gated ML-asset
 * endpoints (design D5/D7).
 *
 * Lists the workspace's mirrored registered models, the feature tables
 * (the `feature_store` tag convention), and the serving/vector
 * endpoints — all mirror-first (ZERO network reads on the page's
 * behalf). Registers models, logs versions, sets/removes aliases,
 * marks/unmarks feature tables, and creates/deletes serving + vector
 * endpoints through the SAME API surface the views expose. Every state
 * shown is the mirror's REPORTED value, never invented. A failed load
 * renders the machine-readable CODE; the flag-off 403 surfaces the
 * distinct banner.
 */
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import type {
  DatabricksMlServingEndpoint,
  UCModelSummary,
  UCTable,
} from '@/shared/types/databricks';

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

const FLAG_DISABLED_CODE = 'DATABRICKS_ML_ASSETS_DISABLED';

interface ServingCreateState {
  name: string;
  config: string;
}

/** Per-model row inputs (the version-log source + the alias pair). */
interface ModelRowState {
  source: string;
  alias: string;
  aliasVersion: string;
}

const EMPTY_ROW: ModelRowState = { source: '', alias: '', aliasVersion: '' };

function errorText(e: unknown): string {
  const code = e instanceof DatabricksApiError ? e.code : undefined;
  const message = e instanceof Error ? e.message : String(e);
  return code ? `[${code}] ${message}` : message;
}

export function MlAssetsPage(): React.ReactElement {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { t } = useTranslation();
  const [models, setModels] = useState<UCModelSummary[]>([]);
  const [featureTables, setFeatureTables] = useState<UCTable[]>([]);
  const [serving, setServing] = useState<DatabricksMlServingEndpoint[]>([]);
  const [vector, setVector] = useState<DatabricksMlServingEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [flagDisabled, setFlagDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [registerName, setRegisterName] = useState('');
  const [rows, setRows] = useState<Record<string, ModelRowState>>({});
  const [servingCreate, setServingCreate] = useState<ServingCreateState>({
    name: '',
    config: '{}',
  });
  const [vectorCreate, setVectorCreate] = useState<ServingCreateState>({
    name: '',
    config: '{}',
  });

  const rowState = (modelId: string): ModelRowState => rows[modelId] ?? EMPTY_ROW;
  const setRowState = (modelId: string, patch: Partial<ModelRowState>) =>
    setRows((prev) => ({ ...prev, [modelId]: { ...rowState(modelId), ...patch } }));

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFlagDisabled(false);
    const id = workspaceId ?? '';
    try {
      const [m, f, s, v] = await Promise.all([
        listMlModels(id),
        listFeatureTables(id),
        listServingEndpoints(id),
        listVectorSearchEndpoints(id),
      ]);
      setModels(m);
      setFeatureTables(f);
      setServing(s);
      setVector(v);
    } catch (e) {
      if (e instanceof DatabricksApiError && e.code === FLAG_DISABLED_CODE) {
        setFlagDisabled(true);
        setModels([]);
        setFeatureTables([]);
        setServing([]);
        setVector([]);
      } else {
        setError(errorText(e));
      }
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const runAction = async (fn: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await fn();
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      void load();
    }
  };

  const register = () =>
    runAction(async () => {
      await registerMlModel(workspaceId ?? '', registerName.trim());
      setRegisterName('');
    });

  const logVersion = (modelId: string, source: string) =>
    runAction(() =>
      logMlModelVersion(workspaceId ?? '', modelId, { source: source.trim() }),
    );

  const setAlias = (modelId: string, alias: string, versionText: string) =>
    runAction(async () => {
      const version = Number(versionText);
      if (!Number.isInteger(version)) {
        throw new Error(t('mlAssets.invalidVersion', 'The version must be an integer'));
      }
      await setMlModelAlias(workspaceId ?? '', modelId, alias.trim(), version);
    });

  const removeAlias = (modelId: string, alias: string) =>
    runAction(() => removeMlModelAlias(workspaceId ?? '', modelId, alias));

  const unmark = (tableId: string) =>
    runAction(() => unmarkFeatureTable(workspaceId ?? '', tableId));

  const parseConfig = (raw: string): Record<string, unknown> => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw.trim() || '{}');
    } catch {
      throw new Error(t('mlAssets.invalidConfigJson', 'The config must be valid JSON'));
    }
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error(t('mlAssets.invalidConfigJson', 'The config must be valid JSON'));
    }
    return parsed as Record<string, unknown>;
  };

  const createServing = () =>
    runAction(async () => {
      await createServingEndpoint(workspaceId ?? '', {
        name: servingCreate.name.trim(),
        config: parseConfig(servingCreate.config),
      });
      setServingCreate({ name: '', config: '{}' });
    });

  const deleteServing = (name: string) =>
    runAction(() => deleteServingEndpoint(workspaceId ?? '', name));

  const createVector = () =>
    runAction(async () => {
      await createVectorSearchEndpoint(workspaceId ?? '', {
        name: vectorCreate.name.trim(),
        config: parseConfig(vectorCreate.config),
      });
      setVectorCreate({ name: '', config: '{}' });
    });

  if (flagDisabled) {
    return (
      <div className="p-4">
        <h2>{t('mlAssets.title', 'ML Assets')}</h2>
        <div role="alert" data-testid="ml-assets-flag-banner">
          {t(
            'mlAssets.flagDisabled',
            'The ML-assets surface is disabled for this tenant',
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div data-testid="ml-assets-loading">{t('mlAssets.loading', 'Loading ML assets...')}</div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <h2>{t('mlAssets.title', 'ML Assets')}</h2>
        <div role="alert" data-testid="ml-assets-error">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2>{t('mlAssets.title', 'ML Assets')}</h2>
      {actionError && (
        <div role="alert" data-testid="ml-assets-action-error">
          {actionError}
        </div>
      )}

      <h3>{t('mlAssets.models', 'Registered models')}</h3>
      <div>
        <input
          type="text"
          data-testid="ml-register-input"
          value={registerName}
          placeholder={t('mlAssets.registerPlaceholder', 'catalog.schema.model')}
          onChange={(e) => setRegisterName(e.target.value)}
        />
        <button type="button" data-testid="ml-register-button" onClick={() => void register()}>
          {t('mlAssets.register', 'Register')}
        </button>
      </div>
      <table data-testid="ml-models-table">
        <thead>
          <tr>
            <th>{t('mlAssets.name', 'Name')}</th>
            <th>{t('mlAssets.fullName', 'Full name')}</th>
            <th>{t('mlAssets.latestVersion', 'Latest version')}</th>
            <th>{t('mlAssets.aliases', 'Aliases')}</th>
            <th>{t('mlAssets.actions', 'Actions')}</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.id}>
              <td>{model.name}</td>
              <td data-testid={`ml-model-full-name-${model.id}`}>{model.full_name}</td>
              <td>{model.latest_version || '-'}</td>
              <td data-testid={`ml-model-aliases-${model.id}`}>
                {model.aliases.map((entry) => (
                  <span key={entry.alias_name}>
                    {entry.alias_name}
                    {entry.version_num ? `→v${entry.version_num}` : ''}{' '}
                    <button
                      type="button"
                      data-testid={`ml-alias-remove-${model.id}-${entry.alias_name}`}
                      onClick={() => void removeAlias(model.id, entry.alias_name)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </td>
              <td>
                <input
                  type="text"
                  data-testid={`ml-version-source-${model.id}`}
                  placeholder={t('mlAssets.sourcePlaceholder', 'dbfs:/ml/...')}
                  value={rowState(model.id).source}
                  onChange={(e) => setRowState(model.id, { source: e.target.value })}
                />
                <button
                  type="button"
                  data-testid={`ml-version-log-${model.id}`}
                  onClick={() => void logVersion(model.id, rowState(model.id).source)}
                >
                  {t('mlAssets.logVersion', 'Log version')}
                </button>
                <input
                  type="text"
                  data-testid={`ml-alias-input-${model.id}`}
                  placeholder={t('mlAssets.aliasPlaceholder', 'champion')}
                  value={rowState(model.id).alias}
                  onChange={(e) => setRowState(model.id, { alias: e.target.value })}
                />
                <input
                  type="number"
                  data-testid={`ml-alias-version-input-${model.id}`}
                  placeholder="1"
                  value={rowState(model.id).aliasVersion}
                  onChange={(e) => setRowState(model.id, { aliasVersion: e.target.value })}
                />
                <button
                  type="button"
                  data-testid={`ml-alias-set-${model.id}`}
                  onClick={() => {
                    const { alias, aliasVersion } = rowState(model.id);
                    if (alias) void setAlias(model.id, alias, aliasVersion);
                  }}
                >
                  {t('mlAssets.setAlias', 'Set alias')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>{t('mlAssets.featureTables', 'Feature tables')}</h3>
      <table data-testid="ml-feature-tables-table">
        <thead>
          <tr>
            <th>{t('mlAssets.name', 'Name')}</th>
            <th>{t('mlAssets.fullName', 'Full name')}</th>
            <th>{t('mlAssets.actions', 'Actions')}</th>
          </tr>
        </thead>
        <tbody>
          {featureTables.map((table) => (
            <tr key={table.id}>
              <td>{table.name}</td>
              <td>{table.full_name}</td>
              <td>
                <button
                  type="button"
                  data-testid={`ml-feature-unmark-${table.id}`}
                  onClick={() => void unmark(table.id)}
                >
                  {t('mlAssets.unmark', 'Unmark')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>{t('mlAssets.serving', 'Serving endpoints')}</h3>
      <div>
        <input
          type="text"
          data-testid="ml-serving-name-input"
          value={servingCreate.name}
          placeholder={t('mlAssets.endpointName', 'endpoint name')}
          onChange={(e) => setServingCreate((s) => ({ ...s, name: e.target.value }))}
        />
        <input
          type="text"
          data-testid="ml-serving-config-input"
          value={servingCreate.config}
          placeholder='{"served_models": []}'
          onChange={(e) => setServingCreate((s) => ({ ...s, config: e.target.value }))}
        />
        <button type="button" data-testid="ml-serving-create" onClick={() => void createServing()}>
          {t('mlAssets.create', 'Create')}
        </button>
      </div>
      <table data-testid="ml-serving-table">
        <thead>
          <tr>
            <th>{t('mlAssets.name', 'Name')}</th>
            <th>{t('mlAssets.state', 'State')}</th>
            <th>{t('mlAssets.actions', 'Actions')}</th>
          </tr>
        </thead>
        <tbody>
          {serving.map((endpoint) => (
            <tr key={endpoint.id}>
              <td>{endpoint.name}</td>
              <td>{endpoint.state || '-'}</td>
              <td>
                <button
                  type="button"
                  data-testid={`ml-serving-delete-${endpoint.name}`}
                  onClick={() => void deleteServing(endpoint.name)}
                >
                  {t('mlAssets.delete', 'Delete')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>{t('mlAssets.vector', 'Vector Search endpoints')}</h3>
      <div>
        <input
          type="text"
          data-testid="ml-vector-name-input"
          value={vectorCreate.name}
          placeholder={t('mlAssets.endpointName', 'endpoint name')}
          onChange={(e) => setVectorCreate((s) => ({ ...s, name: e.target.value }))}
        />
        <input
          type="text"
          data-testid="ml-vector-config-input"
          value={vectorCreate.config}
          placeholder="{}"
          onChange={(e) => setVectorCreate((s) => ({ ...s, config: e.target.value }))}
        />
        <button type="button" data-testid="ml-vector-create" onClick={() => void createVector()}>
          {t('mlAssets.create', 'Create')}
        </button>
      </div>
      <table data-testid="ml-vector-table">
        <thead>
          <tr>
            <th>{t('mlAssets.name', 'Name')}</th>
            <th>{t('mlAssets.state', 'State')}</th>
          </tr>
        </thead>
        <tbody>
          {vector.map((endpoint) => (
            <tr key={endpoint.id}>
              <td>{endpoint.name}</td>
              <td>{endpoint.state || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
