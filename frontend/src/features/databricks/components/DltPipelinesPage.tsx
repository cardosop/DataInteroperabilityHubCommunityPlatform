/**
 * DLT pipelines page (openspec add-databricks-dlt-pipelines task 10.7)
 * — the U5 management surface.
 *
 * Lists the workspace's mirrored DLT pipelines (the 10.2 mirror — zero
 * network reads on the page's behalf) with each pipeline's latest
 * update state, and drives start (full refresh) / stop through the
 * SAME API surface the CLI rides (design D7). Every state is the
 * pipelines API's REPORTED value, never invented. A failed load
 * renders the machine-readable CODE; the flag-off 403 surfaces the
 * distinct banner; a start conflict surfaces the 409 code inline.
 */
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import type { DatabricksDltPipeline } from '@/shared/types/databricks';

import {
  DatabricksApiError,
  listDltPipelines,
  startDltUpdate,
  stopDltPipeline,
} from '../services/dltService';

const FLAG_DISABLED_CODE = 'DATABRICKS_DLT_PIPELINES_DISABLED';
const CONFLICT_CODE = 'DATABRICKS_DLT_UPDATE_CONFLICT';

export function DltPipelinesPage(): React.ReactElement {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { t } = useTranslation();
  const [pipelines, setPipelines] = useState<DatabricksDltPipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [flagDisabled, setFlagDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyPipelineId, setBusyPipelineId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFlagDisabled(false);
    try {
      setPipelines(await listDltPipelines(workspaceId ?? ''));
    } catch (e) {
      if (e instanceof DatabricksApiError && e.code === FLAG_DISABLED_CODE) {
        setFlagDisabled(true);
        setPipelines([]);
      } else {
        const code = e instanceof DatabricksApiError ? e.code : undefined;
        const message = e instanceof Error ? e.message : String(e);
        setError(code ? `[${code}] ${message}` : message);
      }
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const start = async (pipelineId: string) => {
    setBusyPipelineId(pipelineId);
    setActionError(null);
    try {
      await startDltUpdate(workspaceId ?? '', pipelineId, { full_refresh: true });
    } catch (e) {
      const code = e instanceof DatabricksApiError ? e.code : undefined;
      const message = e instanceof Error ? e.message : String(e);
      setActionError(
        code === CONFLICT_CODE
          ? t('dlt.updateConflict', 'An update is already active for this pipeline')
          : code
            ? `[${code}] ${message}`
            : message,
      );
    } finally {
      setBusyPipelineId(null);
      void load();
    }
  };

  const stop = async (pipelineId: string) => {
    setBusyPipelineId(pipelineId);
    setActionError(null);
    try {
      await stopDltPipeline(workspaceId ?? '', pipelineId);
    } catch (e) {
      const code = e instanceof DatabricksApiError ? e.code : undefined;
      const message = e instanceof Error ? e.message : String(e);
      setActionError(code ? `[${code}] ${message}` : message);
    } finally {
      setBusyPipelineId(null);
      void load();
    }
  };

  if (flagDisabled) {
    return (
      <div className="p-4">
        <h2>{t('dlt.title', 'DLT Pipelines')}</h2>
        <div role="alert" data-testid="dlt-flag-banner">
          {t(
            'dlt.flagDisabled',
            'The DLT pipeline management surface is disabled for this tenant',
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return <div data-testid="dlt-loading">{t('dlt.loading', 'Loading DLT pipelines...')}</div>;
  }

  if (error) {
    return (
      <div className="p-4">
        <h2>{t('dlt.title', 'DLT Pipelines')}</h2>
        <div role="alert" data-testid="dlt-error">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2>{t('dlt.title', 'DLT Pipelines')}</h2>
      {actionError && (
        <div role="alert" data-testid="dlt-action-error">
          {actionError}
        </div>
      )}
      {pipelines.length === 0 ? (
        <div data-testid="dlt-empty">{t('dlt.empty', 'No DLT pipelines mirrored yet.')}</div>
      ) : (
        <table data-testid="dlt-pipeline-table">
          <thead>
            <tr>
              <th>{t('dlt.name', 'Name')}</th>
              <th>{t('dlt.state', 'State')}</th>
              <th>{t('dlt.latestUpdate', 'Latest update')}</th>
              <th>{t('dlt.actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {pipelines.map((pipeline) => (
              <tr key={pipeline.id}>
                <td>{pipeline.name}</td>
                <td>{pipeline.state}</td>
                <td>{pipeline.latest_update_state ?? '-'}</td>
                <td>
                  <button
                    type="button"
                    disabled={busyPipelineId === pipeline.id}
                    onClick={() => void start(pipeline.pipeline_id)}
                  >
                    {t('dlt.start', 'Start')}
                  </button>
                  <button
                    type="button"
                    disabled={busyPipelineId === pipeline.id}
                    onClick={() => void stop(pipeline.pipeline_id)}
                  >
                    {t('dlt.stop', 'Stop')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
