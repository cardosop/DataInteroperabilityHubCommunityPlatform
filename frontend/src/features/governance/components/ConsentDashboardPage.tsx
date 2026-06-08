/**
 * DPO — read-only consent dashboard (Phase 232.1).
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../../shared/api/client';

type Dash = {
  purposes: Array<{
    purpose_id: string;
    purpose_key: string;
    name: string;
    active_grants: number;
    revoked_records: number;
  }>;
};

export function ConsentDashboardPage() {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data: body } = await apiClient.getClient().get<Dash>(
          '/api/v1/governance/consent-dashboard/',
        );
        if (!cancelled) setData(body);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load dashboard');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="governance-consent-dashboard" style={{ padding: '1.5rem' }}>
      <p>
        <Link to="/governance">← Back to governance</Link>
      </p>
      <h1>Consent dashboard</h1>
      <p>Aggregate consent posture per purpose (DPO view).</p>
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <table className="table" style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th align="left">Purpose</th>
              <th align="right">Active grants</th>
              <th align="right">Revoked</th>
            </tr>
          </thead>
          <tbody>
            {data.purposes.map((row) => (
              <tr key={row.purpose_id}>
                <td>
                  {row.name} <code>{row.purpose_key}</code>
                </td>
                <td align="right">{row.active_grants}</td>
                <td align="right">{row.revoked_records}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        !error && <p>Loading…</p>
      )}
    </div>
  );
}
