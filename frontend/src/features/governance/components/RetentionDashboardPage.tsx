/**
 * Phase 232.7 — operational snapshot + quarterly audit counts for retention auto-sweep.
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useRetentionDashboard, useRetentionQuarterlyReport } from '../hooks/useRetention';
import './RetentionPolicyListPage.css';

function currentQuarter(d: Date): { year: number; quarter: number } {
  const year = d.getFullYear();
  const quarter = Math.floor(d.getMonth() / 3) + 1;
  return { year, quarter };
}

export function RetentionDashboardPage() {
  const navigate = useNavigate();
  const { year: cy, quarter: cq } = useMemo(() => currentQuarter(new Date()), []);
  const [year, setYear] = useState(cy);
  const [quarter, setQuarter] = useState(cq);

  const dashQ = useRetentionDashboard();
  const qQ = useRetentionQuarterlyReport(`${year}-Q${quarter}`);

  if (dashQ.isLoading) {
    return <ListPageSkeleton />;
  }

  if (dashQ.error || !dashQ.data) {
    return (
      <ErrorDisplay
        error={dashQ.error || new Error('No data')}
        title="Failed to load retention dashboard"
        onRetry={() => dashQ.refetch()}
      />
    );
  }

  const d = dashQ.data;

  return (
    <div className="governance-retention-policy-list-page">
      <div className="governance-detail-header">
        <Button variant="ghost" onClick={() => navigate('/governance/retention')}>
          ← Back to retention policies
        </Button>
      </div>

      <h1>Retention enforcement</h1>
      <p style={{ marginTop: 0, maxWidth: '52rem', opacity: 0.92 }}>
        Snapshot for the automated sweep (tombstone + {d.autosweep_hard_delete_grace_days}-day grace +
        hard-delete). Enable the tenant flag under Settings → feature flags to activate processing.
      </p>

      <section className="governance-detail-section" aria-label="Live metrics">
        <div className="governance-detail-metadata">
          <div className="metadata-item">
            <label>Enabled policies</label>
            <span>{d.enabled_policies}</span>
          </div>
          <div className="metadata-item">
            <label>Awaiting tombstone</label>
            <span>{d.awaiting_initial_tombstone}</span>
          </div>
          <div className="metadata-item">
            <label>Awaiting hard delete</label>
            <span>{d.awaiting_hard_delete_after_grace}</span>
          </div>
          <div className="metadata-item">
            <label>Policies on legal hold</label>
            <span>{d.policies_under_legal_hold}</span>
          </div>
          <div className="metadata-item">
            <label>Generated</label>
            <span>{new Date(d.generated_at ?? '').toLocaleString()}</span>
          </div>
        </div>
      </section>

      <section className="governance-detail-section" aria-label="Quarterly compliance report">
        <h2>Quarterly audit counts</h2>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <label>
            Year{' '}
            <input
              type="number"
              value={year}
              min={2020}
              max={2100}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </label>
          <label>
            Quarter{' '}
            <select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
              <option value={1}>Q1</option>
              <option value={2}>Q2</option>
              <option value={3}>Q3</option>
              <option value={4}>Q4</option>
            </select>
          </label>
        </div>
        {qQ.isLoading && <p>Loading quarterly data…</p>}
        {qQ.error && (
          <ErrorDisplay
            error={qQ.error}
            title="Quarterly report failed"
            onRetry={() => qQ.refetch()}
          />
        )}
        {qQ.data && (
          <div className="governance-detail-metadata">
            <div className="metadata-item">
              <label>Tombstone audit events</label>
              <span>{qQ.data.tombstone_events_in_quarter}</span>
            </div>
            <div className="metadata-item">
              <label>Hard-delete audit events</label>
              <span>{qQ.data.hard_delete_events_in_quarter}</span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
