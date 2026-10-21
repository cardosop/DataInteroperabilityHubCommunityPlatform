/**
 * RootCauseAnalysisPage (Phase 240.4.A.5).
 *
 * Form to select a DQ run (via URL ``:id`` param OR free-text input)
 * and render the resulting root-cause analysis tree with primary
 * cause + recommendations.
 *
 * Data source: ``GET /api/v1/dq/quality/root_cause_analysis/`` via
 * ``useDQRootCauseAnalysis``.
 *
 * Route shape: ``/dq/runs/:id/rca`` AND a free-form fallback at
 * ``/dq/rca`` (mounted by 240.4.A.8).
 */

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useDQRootCauseAnalysis } from '../hooks/useDQ';
import './DQRunResultsViewer.css';

export function RootCauseAnalysisPage() {
  const { id: dqRunIdFromRoute } = useParams<{ id: string }>();
  const [dqRunId, setDqRunId] = useState(dqRunIdFromRoute ?? '');
  const [assetId, setAssetId] = useState('');
  const [lookback, setLookback] = useState(30);

  // Sync URL param → state when the route changes.
  useEffect(() => {
    if (dqRunIdFromRoute) setDqRunId(dqRunIdFromRoute);
  }, [dqRunIdFromRoute]);

  const { data, isLoading, error, refetch } = useDQRootCauseAnalysis({
    dq_run_id: dqRunId.trim() || undefined,
    asset_id: dqRunId.trim() ? undefined : assetId.trim() || undefined,
    lookback_days: lookback,
  });

  const confidencePct = (c: number) => `${(c * 100).toFixed(1)}%`;

  return (
    <div className="dq-results-viewer" data-testid="rca-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Data Quality', href: '/dq' },
          { label: 'Root Cause' },
        ]}
      />

      <div className="dq-results-header">
        <h1>Root Cause Analysis</h1>
        <p className="dq-results-subtitle">
          Identify likely contributing factors for a DQ run's failures or
          warnings.
        </p>
      </div>

      <div className="dq-results-filters">
        <div className="filter-group">
          <label htmlFor="rca-run">DQ Run ID</label>
          <input
            id="rca-run"
            type="text"
            placeholder="UUID..."
            value={dqRunId}
            onChange={(e) => setDqRunId(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="rca-asset">…or Asset ID (latest succeeded run)</label>
          <input
            id="rca-asset"
            type="text"
            placeholder="UUID..."
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
            disabled={!!dqRunId.trim()}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="rca-lookback">Lookback (days)</label>
          <input
            id="rca-lookback"
            type="number"
            min={1}
            max={365}
            value={lookback}
            onChange={(e) =>
              setLookback(Math.max(1, Math.min(365, Number(e.target.value) || 30)))
            }
          />
        </div>
        <div className="filter-group filter-group--bottom-aligned">
          <Button variant="secondary" onClick={() => refetch()}>
            Refresh
          </Button>
        </div>
      </div>

      {!dqRunId.trim() && !assetId.trim() ? (
        <EmptyState
          title="Select a DQ run"
          message="Provide either a DQ run ID OR an asset ID to fetch the root-cause analysis."
        />
      ) : isLoading ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorDisplay
          error={error}
          title="Failed to load root cause analysis"
          onRetry={() => refetch()}
        />
      ) : !data ? null : (
        <>
          <div className="dq-results-summary">
            <div className="summary-card">
              <div className="summary-label">DQ Run</div>
              <div className="summary-value">{data.dq_run_id.slice(0, 8)}…</div>
            </div>
            <div className="summary-card">
              <div className="summary-label">Analysis date</div>
              <div className="summary-value">
                {new Date(data.analysis_date).toLocaleString()}
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-label">Causes detected</div>
              <div className="summary-value">{data.root_causes.length}</div>
            </div>
          </div>

          {data.primary_cause && (
            <section data-testid="rca-primary-cause">
              <h3>Primary cause</h3>
              <div className="category-card">
                <div className="category-name">
                  {data.primary_cause.type}{' '}
                  <span className="status-badge status-warn">
                    {confidencePct(data.primary_cause.confidence)}
                  </span>
                </div>
                <p>{data.primary_cause.description}</p>
              </div>
            </section>
          )}

          <section data-testid="rca-tree">
            <h3>All contributing factors</h3>
            {data.root_causes.length === 0 ? (
              <p>No contributing factors identified.</p>
            ) : (
              <ul className="rca-tree">
                {data.root_causes.map((cause, i) => (
                  <li key={`${cause.type}-${i}`}>
                    <strong>{cause.type}</strong> — {cause.description}{' '}
                    <span className="status-badge status-warn">
                      {confidencePct(cause.confidence)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section data-testid="rca-recommendations">
            <h3>Recommendations</h3>
            {data.recommendations.length === 0 ? (
              <p>No recommendations.</p>
            ) : (
              <ul>
                {data.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
