/**
 * Warehouse Connection Detail Page — Phase 275.D
 * Schema browser, test results, ACL management for a single connection.
 */
import React, { useCallback, useEffect, useState } from 'react';
import type { SchemaReflection, WarehouseConnection } from '@/shared/types/warehouses';
import { getConnection, reflectSchema, testConnection } from '../services/warehouseService';

interface Props { connectionId: string }

export function ConnectionDetailPage({ connectionId }: Props): React.ReactElement {
  const [conn, setConn] = useState<WarehouseConnection | null>(null);
  const [testResult, setTestResult] = useState<string>('');
  const [schema, setSchema] = useState<SchemaReflection | null>(null);
  const [tableName, setTableName] = useState('');

  const load = useCallback(async () => {
    setConn(await getConnection(connectionId));
  }, [connectionId]);

  useEffect(() => { load().catch(console.error); }, [load]);

  const handleTest = async () => {
    setTestResult('Testing...');
    const r = await testConnection(connectionId);
    setTestResult(r.success ? `OK (${r.latency_ms?.toFixed(1)}ms)` : `Failed: ${r.error}`);
  };

  const handleReflect = async () => {
    if (!tableName) return;
    setSchema(await reflectSchema(connectionId, tableName));
  };

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
