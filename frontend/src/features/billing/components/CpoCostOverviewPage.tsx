/**
 * Phase 277.B.031 — CPO cost overview dashboard.
 *
 * Displays aggregated cost breakdown per tenant and per feature category,
 * with month-over-month trend data. Protected behind PLATFORM_ADMIN.
 */
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../../shared/api/client';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { FC } from 'react';
import './CpoCostOverviewPage.css';

const COST_OVERVIEW_PATH = 'billing/admin/cost-overview/';

interface TenantCostRow {
  tenant_id: string;
  tenant_name: string;
  total_cents: number;
  order_count: number;
}

interface FeatureCostRow {
  category: string;
  total_cents: number;
  order_count: number;
}

interface MomEntry {
  year: number;
  month: number;
  total_cents: number;
  order_count: number;
  delta_pct: number | null;
}

interface CostOverview {
  total_cents: number;
  currency: string;
  months_included: number;
  per_tenant: TenantCostRow[];
  per_feature: FeatureCostRow[];
  month_over_month: MomEntry[];
}

function fmtCents(cents: number, currency: string): string {
  const amt = cents / 100;
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(amt);
}

function fmtDelta(pct: number | null): string {
  if (pct === null) return '—';
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct}%`;
}

function monthLabel(entry: MomEntry): string {
  const d = new Date(entry.year, entry.month - 1, 1);
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
}

export const CpoCostOverviewPage: FC = () => {
  const months = 12;
  const { data, isLoading, error, refetch } = useQuery<CostOverview>({
    queryKey: ['billing', 'cost-overview', months],
    queryFn: async () => {
      const resp = await apiClient.getClient().get<CostOverview>(
        `${COST_OVERVIEW_PATH}?months=${months}`,
      );
      return resp.data;
    },
  });

  if (isLoading) return <LoadingSpinner message="Loading cost overview..." />;
  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load cost overview"
        onRetry={() => refetch()}
      />
    );
  }

  if (!data) {
    return <EmptyState title="No cost data" message="No completed payment transactions exist." />;
  }

  return (
    <div className="cpo-cost-overview" data-testid="cpo-cost-overview">
      <header className="cpo-cost-overview__header">
        <h1>Cost Overview</h1>
        <p className="cpo-cost-overview__subtitle">
          Total spend across all tenants &middot; Last {data.months_included} months
        </p>
      </header>

      <section className="cpo-cost-overview__total" data-testid="cost-total">
        <span className="cpo-cost-overview__total-label">Total Spend</span>
        <span className="cpo-cost-overview__total-value">
          {fmtCents(data.total_cents, data.currency)}
        </span>
      </section>

      <div className="cpo-cost-overview__grid">
        {/* Per-Tenant table */}
        <section className="cpo-cost-overview__section">
          <h2>Per Tenant</h2>
          <table className="cpo-cost-overview__table" data-testid="cost-tenant-table">
            <thead>
              <tr>
                <th>Tenant</th>
                <th className="cpo-cost-overview__num">Orders</th>
                <th className="cpo-cost-overview__num">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.per_tenant.map((row) => (
                <tr key={row.tenant_id} data-testid={`cost-tenant-${row.tenant_id}`}>
                  <td>{row.tenant_name}</td>
                  <td className="cpo-cost-overview__num">{row.order_count}</td>
                  <td className="cpo-cost-overview__num">{fmtCents(row.total_cents, data.currency)}</td>
                </tr>
              ))}
              {data.per_tenant.length === 0 && (
                <tr><td colSpan={3} className="cpo-cost-overview__empty">No tenant data</td></tr>
              )}
            </tbody>
          </table>
        </section>

        {/* Per-Feature-Category table */}
        <section className="cpo-cost-overview__section">
          <h2>Per Feature Category</h2>
          <table className="cpo-cost-overview__table" data-testid="cost-feature-table">
            <thead>
              <tr>
                <th>Category</th>
                <th className="cpo-cost-overview__num">Orders</th>
                <th className="cpo-cost-overview__num">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.per_feature.map((row) => (
                <tr key={row.category} data-testid={`cost-feature-${row.category}`}>
                  <td>{row.category}</td>
                  <td className="cpo-cost-overview__num">{row.order_count}</td>
                  <td className="cpo-cost-overview__num">{fmtCents(row.total_cents, data.currency)}</td>
                </tr>
              ))}
              {data.per_feature.length === 0 && (
                <tr><td colSpan={3} className="cpo-cost-overview__empty">No feature data</td></tr>
              )}
            </tbody>
          </table>
        </section>
      </div>

      {/* MoM Trend */}
      <section className="cpo-cost-overview__section">
        <h2>Month-over-Month</h2>
        <table className="cpo-cost-overview__table" data-testid="cost-mom-table">
          <thead>
            <tr>
              <th>Month</th>
              <th className="cpo-cost-overview__num">Orders</th>
              <th className="cpo-cost-overview__num">Total</th>
              <th className="cpo-cost-overview__num">Delta</th>
            </tr>
          </thead>
          <tbody>
            {data.month_over_month.map((entry) => (
              <tr key={`${entry.year}-${entry.month}`} data-testid={`cost-mom-${entry.year}-${entry.month}`}>
                <td>{monthLabel(entry)}</td>
                <td className="cpo-cost-overview__num">{entry.order_count}</td>
                <td className="cpo-cost-overview__num">{fmtCents(entry.total_cents, data.currency)}</td>
                <td className={`cpo-cost-overview__num cpo-cost-overview__delta ${
                  entry.delta_pct !== null && entry.delta_pct > 0 ? 'cpo-cost-overview__delta--up' : ''
                }${
                  entry.delta_pct !== null && entry.delta_pct < 0 ? 'cpo-cost-overview__delta--down' : ''
                }`}>
                  {fmtDelta(entry.delta_pct)}
                </td>
              </tr>
            ))}
            {data.month_over_month.length === 0 && (
              <tr><td colSpan={4} className="cpo-cost-overview__empty">No monthly data</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
};
