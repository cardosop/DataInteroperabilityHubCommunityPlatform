/**
 * TrendsVisualization (Phase 240.4.A.2).
 *
 * Renders a per-asset / per-metric quality trend over a configurable
 * time-range as an inline SVG line-chart (no external chart library
 * is wired into the app — keeping the bundle lean).  Each rendered
 * point carries a direction badge (improving / degrading / stable)
 * driven by the backend ``DQTrendDirection`` value.
 *
 * Data source: ``GET /api/v1/dq/quality/trends/`` via ``useDQTrends``.
 */

import { useMemo, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { exportToCSV } from '../../../shared/utils/exportUtils';
import { DQTrendDirection, type DQTrendsFilters } from '../../../shared/types/dq';
import { useDQTrends } from '../hooks/useDQ';
import './DQRunResultsViewer.css';

const PERIOD_TYPES: Array<NonNullable<DQTrendsFilters['period_type']>> = [
  'HOURLY',
  'DAILY',
  'WEEKLY',
  'MONTHLY',
];

export function TrendsVisualization() {
  const [assetId, setAssetId] = useState('');
  const [metricType, setMetricType] = useState('quality_score');
  const [periodType, setPeriodType] =
    useState<NonNullable<DQTrendsFilters['period_type']>>('DAILY');
  const [timeRange, setTimeRange] = useState(30);

  // Trends require at least an asset_id; until the user supplies one,
  // we don't fire the request (the backend would return [] but it
  // still consumes the daily plan-limit budget).
  const filters: DQTrendsFilters = useMemo(
    () =>
      assetId.trim()
        ? {
            asset_id: assetId.trim(),
            metric_type: metricType,
            period_type: periodType,
            time_range: timeRange,
          }
        : {},
    [assetId, metricType, periodType, timeRange],
  );

  const { data, isLoading, error, refetch } = useDQTrends(filters);
  const trends = data?.results ?? [];

  const directionBadge = (dir: string) => {
    const cls =
      dir === DQTrendDirection.IMPROVING
        ? 'status-pass'
        : dir === DQTrendDirection.DEGRADING
        ? 'status-fail'
        : 'status-warn';
    return <span className={`status-badge ${cls}`}>{dir}</span>;
  };

  const handleExport = () => {
    if (trends.length === 0) return;
    exportToCSV(
      trends.map((t) => ({
        period_start: t.period_start,
        period_end: t.period_end,
        current_value: t.current_value,
        previous_value: t.previous_value,
        change_amount: t.change_amount,
        change_percent: t.change_percent,
        direction: t.direction,
        trend_strength: t.trend_strength,
        forecast_value: t.forecast_value,
      })),
      `dq-trends-${assetId}-${metricType}`,
    );
  };

  // ── Inline SVG line chart ──────────────────────────────────────
  const chart = useMemo(() => {
    if (trends.length === 0) return null;
    const w = 800;
    const h = 240;
    const pad = 36;
    const values = trends.map((t) => t.current_value);
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    const range = Math.max(maxV - minV, 1e-9);

    const x = (i: number) =>
      pad + (i * (w - 2 * pad)) / Math.max(trends.length - 1, 1);
    const y = (v: number) => h - pad - ((v - minV) / range) * (h - 2 * pad);

    const path = trends
      .map((t, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(t.current_value)}`)
      .join(' ');

    return (
      <svg
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label="Quality trend line chart"
        data-testid="trends-chart"
        className="dq-trends-chart"
      >
        <rect x={0} y={0} width={w} height={h} fill="transparent" />
        {/* Grid + axis */}
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#888" />
        <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#888" />
        {/* Min / max labels */}
        <text x={4} y={pad + 4} fontSize="11">
          {maxV.toFixed(1)}
        </text>
        <text x={4} y={h - pad} fontSize="11">
          {minV.toFixed(1)}
        </text>
        {/* Line */}
        <path d={path} stroke="#3b82f6" strokeWidth={2} fill="none" />
        {/* Points */}
        {trends.map((t, i) => (
          <circle
            key={`${t.period_start}-${i}`}
            cx={x(i)}
            cy={y(t.current_value)}
            r={3}
            fill={
              t.direction === DQTrendDirection.IMPROVING
                ? '#10b981'
                : t.direction === DQTrendDirection.DEGRADING
                ? '#ef4444'
                : '#6b7280'
            }
          />
        ))}
      </svg>
    );
  }, [trends]);

  return (
    <div className="dq-results-viewer" data-testid="trends-visualization">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Data Quality', href: '/dq' },
          { label: 'Trends' },
        ]}
      />

      <div className="dq-results-header">
        <h1>DQ Trends</h1>
        <p className="dq-results-subtitle">
          Quality trend visualisation per metric over a configurable time
          range.
        </p>
      </div>

      <div className="dq-results-filters">
        <div className="filter-group">
          <label htmlFor="trend-asset">Asset ID</label>
          <input
            id="trend-asset"
            type="text"
            placeholder="UUID..."
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="trend-metric">Metric type</label>
          <input
            id="trend-metric"
            type="text"
            value={metricType}
            onChange={(e) => setMetricType(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="trend-period">Period</label>
          <select
            id="trend-period"
            value={periodType}
            onChange={(e) =>
              setPeriodType(
                e.target.value as NonNullable<DQTrendsFilters['period_type']>,
              )
            }
          >
            {PERIOD_TYPES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="trend-range">Time range (days)</label>
          <input
            id="trend-range"
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
            disabled={trends.length === 0}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {!assetId.trim() ? (
        <EmptyState
          title="Enter an Asset ID"
          message="Trends are scoped per asset — supply an asset_id above to fetch the trend series."
        />
      ) : isLoading ? (
        <ListPageSkeleton />
      ) : error ? (
        <ErrorDisplay
          error={error}
          title="Failed to load trends"
          onRetry={() => refetch()}
        />
      ) : trends.length === 0 ? (
        <EmptyState
          title="No trends available"
          message="No trend data points have been computed for this asset / metric / period yet."
        />
      ) : (
        <>
          <div className="dq-trends-chart-wrapper">{chart}</div>
          <div className="dq-run-list-table">
            <table>
              <thead>
                <tr>
                  <th>Period start</th>
                  <th>Current</th>
                  <th>Previous</th>
                  <th>Change %</th>
                  <th>Direction</th>
                  <th>Trend strength</th>
                  <th>Forecast</th>
                </tr>
              </thead>
              <tbody>
                {trends.map((t, i) => (
                  <tr key={`${t.period_start}-${i}`}>
                    <td>{new Date(t.period_start).toLocaleDateString()}</td>
                    <td>{t.current_value.toFixed(2)}</td>
                    <td>
                      {t.previous_value !== null
                        ? t.previous_value.toFixed(2)
                        : '—'}
                    </td>
                    <td>
                      {t.change_percent !== null
                        ? `${t.change_percent.toFixed(2)}%`
                        : '—'}
                    </td>
                    <td>{directionBadge(t.direction)}</td>
                    <td>
                      {t.trend_strength !== null
                        ? t.trend_strength.toFixed(2)
                        : '—'}
                    </td>
                    <td>
                      {t.forecast_value !== null
                        ? t.forecast_value.toFixed(2)
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
