/**
 * Live Data Preview Page — Phase 275.D
 * Sample rows from a LIVE_QUERY asset with JSON/Arrow toggle.
 */
import React, { useState } from 'react';

interface Props { assetId: string }

export function LiveDataPreviewPage({ assetId }: Props): React.ReactElement {
  const [rows, setRows] = useState<unknown[][]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [format, setFormat] = useState<'json' | 'arrow'>('json');
  const [loading, setLoading] = useState(false);

  const fetchRows = async (reset = false) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        asset_id: assetId, limit: '100',
        ...(reset ? {} : { cursor: cursor ?? '' }),
      });
      const resp = await fetch(`/api/v1/warehouses/query/?${params}`, {
        headers: format === 'arrow'
          ? { Accept: 'application/vnd.apache.arrow.stream' }
          : { Accept: 'application/json' },
      });
      if (format === 'arrow') {
        const buf = await resp.arrayBuffer();
        setRows([[`Arrow stream: ${buf.byteLength} bytes`]]);
      } else {
        const data = await resp.json();
        setRows(data.rows ?? []);
        setCursor(data.cursor ?? null);
      }
    } finally { setLoading(false); }
  };

  return (
    <div className="live-data-preview">
      <h3>Live Data Preview</h3>
      <div className="controls">
        <select value={format} onChange={e => setFormat(e.target.value as 'json' | 'arrow')}>
          <option value="json">JSON</option>
          <option value="arrow">Apache Arrow</option>
        </select>
        <button onClick={() => fetchRows(true)} disabled={loading}>
          {loading ? 'Loading...' : 'Load'}
        </button>
        {cursor && <button onClick={() => fetchRows(false)} disabled={loading}>Next Page</button>}
      </div>
      {rows.length > 0 && (
        <table><tbody>{rows.map((row, i) => (<tr key={i}>{row.map((cell, j) => (<td key={j}>{String(cell)}</td>))}</tr>))}</tbody></table>
      )}
    </div>
  );
}
