/**
 * Warehouse Connection Wizard — Phase 275.D
 *
 * Create/edit form for warehouse connections.  Collects name, type,
 * credentials (config JSON), region, and optional private endpoint.
 */
import React, { useState } from 'react';

import type { WarehouseConnectionCreatePayload } from '@/shared/types/warehouses';
import { WarehouseType } from '@/shared/types/warehouses';
import { createConnection, updateConnection } from '../services/warehouseService';

interface Props {
  connectionId?: string; // if set, edit mode
  initial?: Partial<WarehouseConnectionCreatePayload>;
  onSaved?: () => void;
}

export function ConnectionWizardPage({
  connectionId,
  initial,
  onSaved,
}: Props): React.ReactElement {
  const [name, setName] = useState(initial?.name ?? '');
  const [warehouseType, setWarehouseType] = useState<WarehouseType>(
    initial?.warehouse_type ?? WarehouseType.SNOWFLAKE,
  );
  const [configJson, setConfigJson] = useState(
    initial?.config ? JSON.stringify(initial.config, null, 2) : '{}',
  );
  const [region, setRegion] = useState(initial?.region ?? '');
  const [endpoint, setEndpoint] = useState(
    initial?.private_endpoint_url ?? '',
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(configJson);
    } catch {
      setError('Config must be valid JSON.');
      return;
    }

    const payload: WarehouseConnectionCreatePayload = {
      name,
      warehouse_type: warehouseType,
      config,
      region: region || undefined,
      private_endpoint_url: endpoint || undefined,
    };

    setSaving(true);
    try {
      if (connectionId) {
        await updateConnection(connectionId, payload);
      } else {
        await createConnection(payload);
      }
      onSaved?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="warehouse-wizard">
      <h2>{connectionId ? 'Edit Connection' : 'New Warehouse Connection'}</h2>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <label>
          Name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Production Snowflake"
          />
        </label>

        <label>
          Warehouse Type
          <select
            value={warehouseType}
            onChange={(e) =>
              setWarehouseType(e.target.value as WarehouseType)
            }
          >
            <option value={WarehouseType.SNOWFLAKE}>Snowflake</option>
            <option value={WarehouseType.BIGQUERY}>BigQuery</option>
            <option value={WarehouseType.DATABRICKS}>Databricks</option>
            <option value={WarehouseType.ATHENA}>Athena</option>
          </select>
        </label>

        <label>
          Credentials (JSON)
          <textarea
            value={configJson}
            onChange={(e) => setConfigJson(e.target.value)}
            rows={8}
            required
            placeholder='{"account": "...", "user": "...", "password": "..."}'
          />
        </label>

        <label>
          Region
          <input
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="e.g. us-east-1"
          />
        </label>

        <label>
          Private Endpoint URL (optional)
          <input
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="e.g. https://privatelink.warehouse.com"
          />
        </label>

        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : connectionId ? 'Update' : 'Create'}
        </button>
      </form>
    </div>
  );
}
