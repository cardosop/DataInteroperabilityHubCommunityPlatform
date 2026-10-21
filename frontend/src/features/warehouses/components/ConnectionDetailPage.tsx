/**
 * Warehouse Connection Detail Page — Phase 275.D
 * Schema browser, test results, ACL management for a single connection.
 */
import React, { useCallback, useEffect, useState } from 'react';
import type { SchemaReflection, WarehouseConnection } from '@/shared/types/warehouses';
import { useToast } from '@/shared/components/Toast/useToast';
import { getErrorMessage } from '@/shared/utils/errorUtils';
import { getConnection, reflectSchema, testConnection } from '../services/warehouseService';

interface Props { connectionId: string }

export function ConnectionDetailPage({ connectionId }: Props): React.ReactElement {
  const toast = useToast();
  const [conn, setConn] = useState<WarehouseConnection | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string>('');
  const [schema, setSchema] = useState<SchemaReflection | null>(null);
  const [tableName, setTableName] = useState('');

  const load = useCallback(async () => {
    setLoadError(null);
    setConn(await getConnection(connectionId));
  }, [connectionId]);

  useEffect(() => {
    load().catch((err: unknown) => {
      // W5.4 (MEDIUM-8) — the load failure was console-only and the page
      // stayed on "Loading..." forever. Surface it.
      setLoadError(getErrorMessage(err) || 'Failed to load connection');
      toast.error(`Couldn't load connection: ${getErrorMessage(err) || 'unknown error'}`);
    });
  }, [load, toast]);

  const handleTest = async () => {
    setTestResult('Testing...');
    try {
      const r = await testConnection(connectionId);
      setTestResult(r.success ? `OK (${r.latency_ms?.toFixed(1)}ms)` : `Failed: ${r.error}`);
    } catch (err) {
      // W5.4 (MEDIUM-8) — previously an unhandled rejection.
      const message = getErrorMessage(err) || 'unknown error';
      setTestResult(`Error: ${message}`);
      toast.error(`Connection test failed: ${message}`);
    }
  };

  const handleReflect = async () => {
    if (!tableName) return;
    try {
      setSchema(await reflectSchema(connectionId, tableName));
    } catch (err) {
      // W5.4 (MEDIUM-8) — previously an unhandled rejection.
      toast.error(`Couldn't reflect schema: ${getErrorMessage(err) || 'unknown error'}`);
    }
  };

  if (loadError) {
    return (
      <div className="connection-detail" role="alert">
        <h2>Connection</h2>
        <p>{loadError}</p>
      </div>
    );
  }

  if (!conn) return <div>Loading...</div>;

  return (
    <div className="connection-detail">
      <h2>{conn.name}</h2>
      <p>Type: {conn.warehouse_type_display} | Region: {conn.region || '—'} | Status: {conn.is_active ? 'Active' : 'Inactive'}</p>

      <button onClick={handleTest}>Test Connection</button>
      {testResult && <span className="test-result">{testResult}</span>}

      <hr />
      <h3>Schema Browser</h3>
      <input value={tableName} onChange={e => setTableName(e.target.value)} placeholder="Table name" />
      <button onClick={handleReflect}>Reflect Schema</button>

      {schema && (
        <table>
          <thead><tr><th>Column</th><th>Type</th><th>Nullable</th><th>Comment</th></tr></thead>
          <tbody>
            {schema.columns.map(c => (
              <tr key={c.name}><td>{c.name}</td><td>{c.data_type}</td><td>{c.nullable ? 'YES' : 'NO'}</td><td>{c.comment || ''}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
