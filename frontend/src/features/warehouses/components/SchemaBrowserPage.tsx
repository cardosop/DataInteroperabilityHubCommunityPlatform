/**
 * Schema Browser Page — Phase 275.D
 * Tree view of warehouse tables/columns from reflect_schema.
 */
import React, { useState } from 'react';
import type { SchemaReflection } from '@/shared/types/warehouses';
import { reflectSchema } from '../services/warehouseService';

interface Props { connectionId: string }

export function SchemaBrowserPage({ connectionId }: Props): React.ReactElement {
  const [table, setTable] = useState('');
  const [schema, setSchema] = useState<SchemaReflection | null>(null);
  const [loading, setLoading] = useState(false);

  const handleReflect = async () => {
    if (!table) return;
    setLoading(true);
    try { setSchema(await reflectSchema(connectionId, table)); }
    finally { setLoading(false); }
  };

  return (
    <div className="schema-browser">
      <h3>Schema Browser</h3>
      <input value={table} onChange={e => setTable(e.target.value)} placeholder="Enter table name..." />
      <button onClick={handleReflect} disabled={loading}>{loading ? 'Loading...' : 'Reflect'}</button>
      {schema && (
        <ul className="schema-tree">
          <li className="table-node">
            📊 {schema.table} ({schema.warehouse_type})
            <ul>
              {schema.columns.map(c => (
                <li key={c.name} className="column-node">
                  {c.nullable ? '◇' : '◆'} {c.name}: {c.data_type}
                  {c.comment && <span className="comment"> — {c.comment}</span>}
                </li>
              ))}
            </ul>
          </li>
        </ul>
      )}
    </div>
  );
}
