/**
 * Warehouse Connection List Page — Phase 275.D
 *
 * Lists all warehouse connections for the current tenant with status,
 * type badges, quick-test, and create/delete actions.  Gated behind
 * ``warehouse_connectivity_enabled`` tenant flag.
 */
import React, { useCallback, useEffect, useState } from 'react';

import type { WarehouseConnection } from '@/shared/types/warehouses';
import { WarehouseType } from '@/shared/types/warehouses';
import {
  deleteConnection,
  listConnections,
  testConnection,
} from '../services/warehouseService';

const TYPE_BADGES: Record<string, string> = {
  [WarehouseType.SNOWFLAKE]: '❄️ Snowflake',
  [WarehouseType.BIGQUERY]: '🔵 BigQuery',
  [WarehouseType.DATABRICKS]: '🧱 Databricks',
  [WarehouseType.ATHENA]: '⚡ Athena',
};

export function ConnectionListPage(): React.ReactElement {
  const [connections, setConnections] = useState<WarehouseConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      setConnections(await listConnections());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch().catch(console.error);
  }, [fetch]);

  const handleTest = async (id: string) => {
    setTestResults((p) => ({ ...p, [id]: 'Testing...' }));
    try {
      const r = await testConnection(id);
      setTestResults((p) => ({
        ...p,
        [id]: r.success
          ? `OK (${r.latency_ms?.toFixed(1)}ms)`
          : `Failed: ${r.error ?? 'unknown'}`,
      }));
    } catch (e) {
      setTestResults((p) => ({ ...p, [id]: `Error: ${String(e)}` }));
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete connection "${name}"?`)) return;
    await deleteConnection(id);
    setConnections((p) => p.filter((c) => c.id !== id));
  };

  if (loading) return <div>Loading connections...</div>;

  return (
    <div className="warehouse-connection-list">
      <h2>Warehouse Connections</h2>
      <a href="/warehouses/new" className="btn-primary">
        + New Connection
      </a>
      {connections.length === 0 ? (
        <p>No warehouse connections configured.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Region</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {connections.map((c) => (
              <tr key={c.id}>
                <td>
                  <a href={`/warehouses/connections/${c.id}`}>{c.name}</a>
                </td>
                <td>{TYPE_BADGES[c.warehouse_type] ?? c.warehouse_type}</td>
                <td>{c.region || '—'}</td>
                <td>{c.is_active ? '✅ Active' : '⏸️ Inactive'}</td>
                <td>
                  <button onClick={() => handleTest(c.id)}>Test</button>
                  <button
                    onClick={() => handleDelete(c.id, c.name)}
                    style={{ color: 'red' }}
                  >
                    Delete
                  </button>
                  {testResults[c.id] && (
                    <span className="test-result">{testResults[c.id]}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
