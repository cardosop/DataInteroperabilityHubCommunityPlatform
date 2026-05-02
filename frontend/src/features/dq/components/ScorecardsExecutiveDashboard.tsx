/**
 * ScorecardsExecutiveDashboard (Phase 240.4.A.3).
 *
 * Aggregate cards (overall pass-rate, avg score, top failing assets,
 * run volume by engine).  Two modes from the same backend endpoint
 * (``GET /api/v1/dq/quality/scorecards/``):
 *  - tenant-level executive dashboard (no ``asset_id``)
 *  - per-asset drill-down (``asset_id`` set)
 *
 * The two payloads are discriminated by the presence of ``asset_id``
 * in the response (per backend contract).
 */

import { useMemo, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { exportToCSV } from '../../../shared/utils/exportUtils';
import { useDQScorecards } from '../hooks/useDQ';
import type {
  DQAssetScorecard,
  DQExecutiveDashboard,
} from '../../../shared/types/dq';
import './DQRunResultsViewer.css';

function isAssetScorecard(
  payload: DQExecutiveDashboard | DQAssetScorecard | undefined,
): payload is DQAssetScorecard {
  return !!payload && 'asset_id' in payload;
}

export function ScorecardsExecutiveDashboard() {
  const [assetId, setAssetId] = useState('');
  const [timeRange, setTimeRange] = useState(30);

  const { data, isLoading, error, refetch } = useDQScorecards({
    asset_id: assetId.trim() || undefined,
    time_range: timeRange,
  });

  const exportRows = useMemo(() => {
    if (!data) return [];
    if (isAssetScorecard(data)) {
      return [
        {
          asset_id: data.asset_id,
          period_days: data.period.days,
          total_runs: data.metrics.total_runs,
          avg_quality_score: data.metrics.avg_quality_score,
          pass_rate: data.metrics.pass_rate,
          fail_rate: data.metrics.fail_rate,
        },
      ];
    }
    return [
      {
        period_days: data.period.days,
        total_runs: data.summary.total_runs,
        avg_quality_score: data.summary.avg_quality_score,
        pass_rate: data.summary.pass_rate,
        fail_rate: data.summary.fail_rate,
        warn_count: data.summary.warn_count,
      },
    ];
  }, [data]);

  const handleExport = () => {
    if (exportRows.length === 0) return;
    // The asset-scoped and tenant-scoped branches above produce
    // arrays with different column shapes (asset-scoped includes
    // ``asset_id``; tenant-scoped includes ``warn_count``). The
    // resulting union confuses ``exportToCSV``'s generic-parameter
    // inference (it picks the first branch's shape and rejects the
    // other). Assert to ``Record<string, unknown>[]`` so the shared
    // CSV builder treats both shapes uniformly — it serialises by
    // key iteration regardless of the literal type.
    exportToCSV(
      exportRows as Array<Record<string, unknown>>,
      `dq-scorecard-${assetId.trim() || 'tenant'}`,
    );
  };

  return (
    <div className="dq-results-viewer" data-testid="scorecards-dashboard">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Data Quality', href: '/dq' },
          { label: 'Scorecards' },
        ]}
      />

      <div className="dq-results-header">
        <h1>DQ Scorecards</h1>
        <p className="dq-results-subtitle">
          Executive dashboard of tenant-wide quality metrics.  Supply an
          asset ID to drill down.
        </p>
      </div>

      <div className="dq-results-filters">
        <div className="filter-group">
          <label htmlFor="sc-asset">Asset ID (optional)</label>
          <input
            id="sc-asset"
            type="text"
            placeholder="leave blank for tenant-level dashboard"
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="sc-range">Time range (days)</label>
          <input
            id="sc-range"
            type="number"
            min={1}
            max={365}
            value={timeRange}
            onChange={(e) =>
              setTimeRange(Math.max(1, Math.min(365, Number(e.target.value) || 30)))
            }
          />
        </div>
        <div className="filter-group filter-group--bottom-aligned">
          <Button
            variant="secondary"
            onClick={handleExport}
            disabled={!data}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorDisplay
          error={error}
          title="Failed to load scorecard"
          onRetry={() => refetch()}
        />
      ) : isAssetScorecard(data) ? (
        <AssetScorecardView data={data} />
      ) : data ? (
        <ExecutiveDashboardView data={data} />
      ) : null}
    </div>
  );
}

function ExecutiveDashboardView({ data }: { data: DQExecutiveDashboard }) {
  return (
    <div data-testid="executive-dashboard">
      <div className="dq-results-summary">
        <div className="summary-card">
          <div className="summary-label">Total Runs</div>
          <div className="summary-value">{data.summary.total_runs}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Avg Quality Score</div>
          <div className="summary-value quality-score">
            {data.summary.avg_quality_score.toFixed(2)}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Pass Rate</div>
          <div className="summary-value passed">
            {data.summary.pass_rate.toFixed(1)}%
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Fail Rate</div>
          <div className="summary-value failed">
            {data.summary.fail_rate.toFixed(1)}%
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Warnings</div>
          <div className="summary-value warning">{data.summary.warn_count}</div>
        </div>
      </div>

      <h3>Score distribution</h3>
      <div className="dq-results-category-breakdown">
        <div className="category-breakdown-grid">
          {Object.entries(data.score_distribution).map(([bucket, count]) => (
            <div key={bucket} className="category-card">
              <div className="category-name">{bucket.toUpperCase()}</div>
              <div className="category-stats">
                <span className="stat-item">
                  Runs: <strong>{count}</strong>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <h3>Top quality issues</h3>
      <div className="dq-run-list-table">
        <table>
          <thead>
            <tr>
              <th>Issue</th>
              <th>Count</th>
              <th>% of runs</th>
            </tr>
          </thead>
          <tbody>
            {data.top_issues.length === 0 ? (
              <tr>
                <td colSpan={3}>No top issues for this period.</td>
              </tr>
            ) : (
              data.top_issues.map((issue) => (
                <tr key={issue.issue}>
                  <td>{issue.issue}</td>
                  <td>{issue.count}</td>
                  <td>{issue.percentage.toFixed(2)}%</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <h3>Trend summary</h3>
      <div className="dq-results-summary">
        <div className="summary-card">
          <div className="summary-label">Improving</div>
          <div className="summary-value passed">
            {data.trend_summary.improving} ({data.trend_summary.improving_percent.toFixed(1)}%)
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Degrading</div>
          <div className="summary-value failed">
            {data.trend_summary.degrading} ({data.trend_summary.degrading_percent.toFixed(1)}%)
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Stable</div>
          <div className="summary-value">{data.trend_summary.stable}</div>
        </div>
      </div>
    </div>
  );
}

function AssetScorecardView({ data }: { data: DQAssetScorecard }) {
  return (
    <div data-testid="asset-scorecard">
      <p>
        <strong>Asset:</strong> {data.asset_id}
      </p>
      <div className="dq-results-summary">
        <div className="summary-card">
          <div className="summary-label">Total Runs</div>
          <div className="summary-value">{data.metrics.total_runs}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Avg Quality Score</div>
          <div className="summary-value quality-score">
            {data.metrics.avg_quality_score.toFixed(2)}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Pass Rate</div>
          <div className="summary-value passed">
            {data.metrics.pass_rate.toFixed(1)}%
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Fail Rate</div>
          <div className="summary-value failed">
            {data.metrics.fail_rate.toFixed(1)}%
          </div>
        </div>
      </div>

      <h3>Recent runs</h3>
      <div className="dq-run-list-table">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Quality Score</th>
              <th>Overall Status</th>
              <th>Completed</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_runs.length === 0 ? (
              <tr>
                <td colSpan={4}>No runs in this period.</td>
              </tr>
            ) : (
              data.recent_runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.id.slice(0, 8)}…</td>
                  <td>{run.quality_score?.toFixed(2) ?? '—'}</td>
                  <td>{run.overall_status ?? '—'}</td>
                  <td>
                    {run.completed_at
                      ? new Date(run.completed_at).toLocaleString()
                      : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
