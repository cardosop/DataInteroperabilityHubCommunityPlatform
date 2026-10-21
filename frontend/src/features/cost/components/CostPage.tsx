/**
 * Cost Tracking Page (UC-TA-007)
 * Displays cost summary, breakdown, by-asset, recommendations for tenant admin.
 * Route: /settings/cost
 */

import { useEffect, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import type {
  CostByAsset,
  CostRecommendations,
  CostSummary,
  CostTrends,
} from '../../../shared/types/cost';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { costService } from '../services/costService';
import './CostPage.css';

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(amount);
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    storage: 'Storage',
    api_calls: 'API calls',
    ingestion: 'Scheduled ingestion',
    export: 'Scheduled export',
  };
  return labels[category] ?? category;
}

export function CostPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [byAsset, setByAsset] = useState<CostByAsset | null>(null);
  const [recommendations, setRecommendations] = useState<CostRecommendations | null>(null);
  const [trends, setTrends] = useState<CostTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sum, asset, rec, tr] = await Promise.all([
        costService.getSummary(),
        costService.getByAsset(),
        costService.getRecommendations(),
        costService.getTrends({ months: 6 }),
      ]);
      setSummary(sum);
      setByAsset(asset);
      setRecommendations(rec);
      setTrends(tr);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  if (loading && !summary) {
    return <LoadingSpinner message="Loading cost data..." />;
  }

  if (error && !summary) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load cost data"
        onRetry={() => loadAll()}
      />
    );
  }

  return (
    <div className="cost-page" data-testid="cost-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Cost' },
        ]}
      />
      <div className="cost-page-header">
        <h1>Cost Tracking</h1>
        <p className="cost-page-description">
          View cost breakdown by category and asset. Usage is converted to estimated costs.
        </p>
      </div>

      {summary && (
        <section className="cost-section cost-summary" aria-labelledby="cost-summary-heading">
          <h2 id="cost-summary-heading">Cost Summary</h2>
          <p className="cost-period">
            Period: {formatDate(summary.period_start)} – {formatDate(summary.period_end)}
          </p>
          <div className="cost-total">
            <span className="cost-total-label">Total estimated cost</span>
            <span className="cost-total-value">{formatCurrency(summary.total_cost)}</span>
          </div>
          <div className="cost-breakdown">
            <h3>Breakdown by category</h3>
            <ul className="cost-breakdown-list">
              {summary.breakdown.map((item) => (
                <li key={item.category} className="cost-breakdown-item">
                  <span className="cost-breakdown-category">
                    {categoryLabel(item.category)}
                  </span>
                  <span className="cost-breakdown-amount">
                    {formatCurrency(item.amount_usd)}
                  </span>
                  {item.quantity != null && (
                    <span className="cost-breakdown-quantity">
                      ({typeof item.quantity === 'number' && item.quantity >= 1000
                        ? item.quantity.toLocaleString()
                        : item.quantity}{' '}
                      {item.category === 'storage' ? 'GB' : item.category === 'api_calls' ? 'calls' : ''})
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {byAsset && byAsset.by_asset.length > 0 && (
        <section className="cost-section cost-by-asset" aria-labelledby="cost-by-asset-heading">
          <h2 id="cost-by-asset-heading">Cost by Asset</h2>
          <p className="cost-section-desc">Storage cost allocated per asset.</p>
          <table className="cost-asset-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th>Storage (GB)</th>
                <th>Cost (USD)</th>
              </tr>
            </thead>
            <tbody>
              {byAsset.by_asset.map((row) => (
                <tr key={row.asset_id}>
                  <td>
                    <span className="cost-asset-name">{row.asset_name}</span>
                    <span className="cost-asset-key">{row.asset_key}</span>
                  </td>
                  <td>{row.storage_gb.toFixed(4)}</td>
                  <td>{formatCurrency(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="cost-asset-total">
            Total (storage): {formatCurrency(byAsset.total_cost)}
          </p>
        </section>
      )}

      {recommendations && recommendations.recommendations.length > 0 && (
        <section className="cost-section cost-recommendations" aria-labelledby="cost-rec-heading">
          <h2 id="cost-rec-heading">Recommendations</h2>
          <ul className="cost-rec-list">
            {recommendations.recommendations.map((rec, idx) => (
              <li
                key={idx}
                className={`cost-rec-item cost-rec-${rec.severity}`}
              >
                {rec.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      {trends && trends.trends.length > 0 && (
        <section className="cost-section cost-trends" aria-labelledby="cost-trends-heading">
          <h2 id="cost-trends-heading">Cost Trends</h2>
          <p className="cost-section-desc">Last 6 months.</p>
          <ul className="cost-trends-list">
            {trends.trends.map((t, idx) => (
              <li key={idx} className="cost-trend-item">
                <span className="cost-trend-period">
                  {formatDate(t.period_start)} – {formatDate(t.period_end)}
                </span>
                <span className="cost-trend-value">{formatCurrency(t.total_cost)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {summary && summary.total_cost === 0 && !byAsset?.by_asset.length && (
        <p className="cost-no-data">No cost data for this period. Usage will appear as costs once resources are used.</p>
      )}
    </div>
  );
}
