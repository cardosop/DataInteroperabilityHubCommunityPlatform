/**
 * AnomaliesDashboard (Phase 240.4.A.1).
 *
 * Tabular view of detected DQ anomalies for the requesting tenant
 * with filters by severity / asset and a drill-down link back to the
 * source DQRun.  Reuses the ``DQRunResultsViewer`` filter/table styling
 * (same .css module is imported below) so the look-and-feel stays
 * consistent across the DQ feature.
 *
 * Data source: ``GET /api/v1/dq/quality/anomalies/`` via
 * ``useDQAnomalies``.
 */

import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { exportToCSV } from '../../../shared/utils/exportUtils';
import {
  DQAnomalySeverity,
  DQ_CATEGORIES,
  DQ_SEVERITIES,
  type DQAnomaliesFilters,
} from '../../../shared/types/dq';
import { useDQAnomalies } from '../hooks/useDQ';
import './DQRunResultsViewer.css';

export function AnomaliesDashboard() {
  const [severity, setSeverity] = useState<DQAnomalySeverity | ''>('');
  const [assetId, setAssetId] = useState('');
  const [metricType, setMetricType] = useState('');
  const [since, setSince] = useState('');

  const filters: DQAnomaliesFilters = useMemo(
    () => ({
      severity: severity || undefined,
      asset_id: assetId.trim() || undefined,
      since: since || undefined,
    }),
    [severity, assetId, since],
  );

  const { data, isLoading, error, refetch } = useDQAnomalies(filters);
  const anomalies = data?.results ?? [];

  const filtered = useMemo(() => {
    if (!metricType) return anomalies;
    return anomalies.filter((a) => a.metric_type === metricType);
  }, [anomalies, metricType]);

  const distinctMetricTypes = useMemo(
    () => Array.from(new Set(anomalies.map((a) => a.metric_type))).sort(),
    [anomalies],
  );

  const handleExport = () => {
    if (filtered.length === 0) return;
    exportToCSV(
      filtered.map((a) => ({
        id: a.id,
        severity: a.severity,
        anomaly_type: a.anomaly_type,
        metric_type: a.metric_type,
        expected_value: a.expected_value,
        actual_value: a.actual_value,
        deviation: a.deviation,
        description: a.description,
        asset_id: a.asset_id,
        dataset_id: a.dataset_id,
        dq_run_id: a.dq_run_id,
        detected_at: a.detected_at,
        acknowledged: a.acknowledged,
      })),
      'dq-anomalies',
    );
  };

  return (
    <div className="dq-results-viewer" data-testid="anomalies-dashboard">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Data Quality', href: '/dq' },
          { label: 'Anomalies' },
        ]}
      />

      <div className="dq-results-header">
        <h1>DQ Anomalies</h1>
        <p className="dq-results-subtitle">
          Statistical anomalies detected across your DQ runs.
        </p>
      </div>

      <div className="dq-results-filters">
        <div className="filter-group">
          <label htmlFor="anom-severity">Severity</label>
          <select
            id="anom-severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as DQAnomalySeverity | '')}
          >
            <option value="">All Severities</option>
            {DQ_SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="anom-asset">Asset ID</label>
          <input
            id="anom-asset"
            type="text"
            placeholder="UUID..."
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label htmlFor="anom-metric">Metric type</label>
          <select
            id="anom-metric"
            value={metricType}
            onChange={(e) => setMetricType(e.target.value)}
          >
            <option value="">All Metrics</option>
            {DQ_CATEGORIES.map((c) => (
              <option key={c} value={c.toLowerCase()}>
                {c}
              </option>
            ))}
            {distinctMetricTypes
              .filter((m) => !DQ_CATEGORIES.includes(m.toUpperCase() as never))
              .map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="anom-since">Detected since</label>
          <input
            id="anom-since"
            type="datetime-local"
            value={since}
            onChange={(e) =>
              setSince(e.target.value ? `${e.target.value}:00Z` : '')
            }
          />
        </div>

        <div className="filter-group filter-group--bottom-aligned">
          <Button
            variant="secondary"
            onClick={handleExport}
            disabled={filtered.length === 0}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {isLoading ? (
        <ListPageSkeleton />
      ) : error ? (
        <ErrorDisplay
          error={error}
          title="Failed to load anomalies"
          onRetry={() => refetch()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No anomalies"
          message="No anomalies match the current filters. New anomalies are detected automatically as DQ runs complete."
        />
      ) : (
        <div className="dq-run-list-table">
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Type</th>
                <th>Metric</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Deviation</th>
                <th>Description</th>
                <th>Detected</th>
                <th>Source DQ Run</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span
                      className={`status-badge status-${a.severity.toLowerCase()}`}
                      data-testid={`anom-severity-${a.id}`}
                    >
                      {a.severity}
                    </span>
                  </td>
                  <td>{a.anomaly_type}</td>
                  <td>{a.metric_type}</td>
                  <td>{a.expected_value ?? '—'}</td>
                  <td>{a.actual_value}</td>
                  <td>{Number.isFinite(a.deviation) ? a.deviation.toFixed(2) : '—'}</td>
                  <td>{a.description || '—'}</td>
                  <td>
                    {a.detected_at
                      ? new Date(a.detected_at).toLocaleString()
                      : '—'}
                  </td>
                  <td>
                    {a.dq_run_id ? (
                      <Link to={`/dq/runs/${a.dq_run_id}`}>
                        {a.dq_run_id.slice(0, 8)}…
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
