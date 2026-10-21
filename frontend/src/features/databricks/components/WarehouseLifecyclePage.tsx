/**
 * SQL-warehouse lifecycle page (openspec add-databricks-sql-warehouses
 * task 3.7) — the U5 non-blocking lifecycle surface.
 *
 * Lists the workspace's mirrored SQL warehouses (the 3.2 mirror — zero
 * network reads) with their reported lifecycle state, and hosts the
 * Start/Stop actions. Actions are NON-BLOCKING: the row flips to an
 * in-flight state (aria-busy, button disabled) while the call is in
 * flight, and renders the compute API's NEW state when it lands — the
 * Hub never invents a state (the mirror contract). A failed action
 * renders the machine-readable CODE in the alert (the 0.15 review
 * parity fix); the flag-off 403 surfaces the distinct banner.
 */
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import type { SqlWarehouse, SqlWarehouseState } from '@/shared/types/databricks';

import {
  DatabricksApiError,
  listWarehouses,
  startWarehouse,
  stopWarehouse,
} from '../services/warehouseService';

const FLAG_DISABLED_CODE = 'DATABRICKS_CONTROL_PLANE_DISABLED';

type PendingAction = 'start' | 'stop';

function actionsFor(state: SqlWarehouseState): PendingAction[] {
  switch (state) {
    case 'STOPPED':
      return ['start'];
    case 'STOPPING':
      return ['start'];
    case 'RUNNING':
      return ['stop'];
    case 'STARTING':
      return ['stop'];
    default: // DELETING — no actions
      return [];
  }
}

export function WarehouseLifecyclePage(): React.ReactElement {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { t } = useTranslation();
  const [rows, setRows] = useState<SqlWarehouse[]>([]);
  const [loading, setLoading] = useState(true);
  const [flagDisabled, setFlagDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, PendingAction>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFlagDisabled(false);
    try {
      setRows(await listWarehouses(workspaceId ?? ''));
    } catch (e) {
      if (e instanceof DatabricksApiError && e.code === FLAG_DISABLED_CODE) {
        setFlagDisabled(true);
        setRows([]);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const runAction = async (row: SqlWarehouse, action: PendingAction) => {
    const id = row.warehouse_id;
    setPending((current) => ({ ...current, [id]: action }));
    setError(null);
    try {
      const updated =
        action === 'start'
          ? await startWarehouse(workspaceId ?? '', id)
          : await stopWarehouse(workspaceId ?? '', id);
      setRows((current) => current.map((r) => (r.warehouse_id === id ? updated : r)));
    } catch (e) {
      const code = e instanceof DatabricksApiError ? e.code : undefined;
      const message = e instanceof Error ? e.message : String(e);
      setError(code ? `[${code}] ${message}` : message);
    } finally {
      setPending((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
    }
  };

  if (loading) {
    return <div className="warehouse-list">{t('databricks.warehouses.loading', 'Loading SQL warehouses…')}</div>;
  }

  if (flagDisabled) {
    return (
      <div role="alert" data-testid="flag-disabled-banner">
        <h2>{t('databricks.warehouses.title', 'SQL warehouses')}</h2>
        <p>
          {t('databricks.page.flag_disabled_body', 'The Databricks control plane is disabled for this tenant.')}{' '}
          <code>{FLAG_DISABLED_CODE}</code>
        </p>
      </div>
    );
  }

  return (
    <div className="warehouse-list">
      <div className="warehouse-list-header">
        <h2>{t('databricks.warehouses.title', 'SQL warehouses')}</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {t('databricks.warehouses.refresh', 'Refresh')}
        </button>
      </div>

      {error && (
        <div role="alert" className="warehouse-error" data-testid="action-error">
          {error}
        </div>
      )}

      {rows.length === 0 ? (
        <p>{t('databricks.warehouses.empty', 'No SQL warehouses reported for this workspace yet.')}</p>
      ) : (
        <table aria-label={t('databricks.warehouses.title', 'SQL warehouses')}>
          <thead>
            <tr>
              <th>{t('databricks.warehouses.name', 'Name')}</th>
              <th>{t('databricks.warehouses.state', 'State')}</th>
              <th>{t('databricks.warehouses.type', 'Type')}</th>
              <th>{t('databricks.warehouses.size', 'Size')}</th>
              <th>{t('databricks.warehouses.actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const inFlight = pending[row.warehouse_id];
              return (
                <tr
                  key={row.warehouse_id}
                  aria-busy={inFlight !== undefined}
                  data-state={row.state}
                >
                  <td>{row.name}</td>
                  <td>{row.state}</td>
                  <td>{row.serverless ? t('databricks.warehouses.serverless', 'serverless') : t('databricks.warehouses.classic', 'classic')}</td>
                  <td>{row.size ?? '-'}</td>
                  <td>
                    {actionsFor(row.state).map((action) => (
                      <button
                        key={action}
                        type="button"
                        data-warehouse={row.warehouse_id}
                        disabled={inFlight !== undefined}
                        onClick={() => void runAction(row, action)}
                      >
                        {action === 'start'
                          ? t('databricks.warehouses.start', 'Start')
                          : t('databricks.warehouses.stop', 'Stop')}
                      </button>
                    ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
