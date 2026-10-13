/**
 * DatabricksWarehousePicker (openspec wire-databricks-dlt-movement task
 * 6.8, design D8) — the workspace+warehouse picker replacing the
 * placeholder http_path.
 *
 * The stored value is the DERIVED `/sql/1.0/warehouses/{id}` path (the
 * 3.6 derivation contract — the backend's `resolve_warehouse_id` accepts
 * both the bare id and this path form, sql_statements.py) — derived from
 * the picked warehouse, NEVER a hand-typed string. The chosen workspace's
 * host rides along for the source config.
 */
import { useEffect, useMemo, useState } from 'react';

import type { DatabricksWorkspace, SqlWarehouse } from '@/shared/types/databricks';
import { listWorkspaces } from '../../databricks/services/databricksService';
import {
  DatabricksApiError,
  listWarehouses,
} from '../../databricks/services/warehouseService';
import {
  deriveWarehouseHttpPath,
  warehouseIdFromHttpPath,
} from '../httpPath';

function classify(err: unknown): string {
  if (err instanceof DatabricksApiError && err.code) {
    return `Failed to load: ${err.code}`;
  }
  return `Failed to load: ${String(err)}`;
}

interface Props {
  /** The stored http_path when editing; undefined on create. */
  value?: string;
  /** Called with the derived path (undefined while nothing is picked). */
  onChange: (httpPath: string | undefined) => void;
  /** Called with the chosen workspace's host (undefined while unpicked). */
  onHostChange?: (host: string | undefined) => void;
}

export function DatabricksWarehousePicker({
  value,
  onChange,
  onHostChange,
}: Props): React.ReactElement {
  const [workspaces, setWorkspaces] = useState<DatabricksWorkspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState('');
  const [warehouses, setWarehouses] = useState<SqlWarehouse[]>([]);
  const [warehouseId, setWarehouseId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const storedWarehouseId = useMemo(() => warehouseIdFromHttpPath(value), [value]);

  useEffect(() => {
    let cancelled = false;
    listWorkspaces()
      .then((rows) => {
        if (!cancelled) {
          setWorkspaces(rows);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(classify(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectWorkspace = (id: string) => {
    setWorkspaceId(id);
    setWarehouseId('');
    setWarehouses([]);
    setError(null);
    onChange(undefined);
    const workspace = workspaces.find((w) => w.id === id);
    onHostChange?.(workspace?.host);
    if (!id) {
      return;
    }
    setLoading(true);
    listWarehouses(id)
      .then((rows) => {
        setWarehouses(rows);
        // Edit mode: pre-select the stored warehouse once its list lands.
        if (
          storedWarehouseId &&
          rows.some((row) => row.warehouse_id === storedWarehouseId)
        ) {
          setWarehouseId(storedWarehouseId);
          onChange(deriveWarehouseHttpPath(storedWarehouseId));
        }
      })
      .catch((err) => setError(classify(err)))
      .finally(() => setLoading(false));
  };

  const selectWarehouse = (id: string) => {
    setWarehouseId(id);
    onChange(id ? deriveWarehouseHttpPath(id) : undefined);
  };

  return (
    <div className="databricks-warehouse-picker">
      <label>
        Workspace
        <select
          aria-label="Workspace"
          value={workspaceId}
          onChange={(e) => selectWorkspace(e.target.value)}
        >
          <option value="">Select a workspace…</option>
          {workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Warehouse
        <select
          aria-label="Warehouse"
          value={warehouseId}
          onChange={(e) => selectWarehouse(e.target.value)}
          disabled={!workspaceId || !warehouses.length}
        >
          <option value="">
            {loading ? 'Loading…' : 'Select a warehouse…'}
          </option>
          {warehouses.map((warehouse) => (
            <option key={warehouse.warehouse_id} value={warehouse.warehouse_id}>
              {warehouse.name}
            </option>
          ))}
        </select>
      </label>

      {error && (
        <div className="picker-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
