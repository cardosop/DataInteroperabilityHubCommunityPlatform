/**
 * Phase 235.5 — Consolidated PLATFORM_ADMIN dashboard widgets.
 *
 * Renders six widget cards on top of the Admin → Overview tab. Each
 * widget summarises a distinct subsystem (tenants, webhooks, audit,
 * compliance, billing, governance) AND links to the deeper feature
 * page so the operator can drill in (spec 235.5.8).
 *
 * Data source: a single ``useAdminDashboardSummary`` query. The
 * server caches the aggregate for 5 minutes, so the polling cost is
 * trivial — every poll past the first within a 5-minute window
 * returns the cached payload.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useAdminDashboardSummary,
  useRefreshAdminDashboardSummary,
} from '../hooks/useAdmin';
import type {
  AdminDashboardAuditWidget,
  AdminDashboardBillingWidget,
  AdminDashboardComplianceWidget,
  AdminDashboardGovernanceWidget,
  AdminDashboardTenantsWidget,
  AdminDashboardWebhooksWidget,
  AdminDashboardWidgetError,
} from '../services/adminService';
import { isWidgetError } from '../services/adminService';
import './DashboardOverview.css';

interface OverviewProps {
  /** Click handler for the Tenants widget — switches the parent's
   *  active tab when the in-page Tenants pane lives in the same view. */
  onOpenTenantsTab?: () => void;
}

export function DashboardOverview({ onOpenTenantsTab }: OverviewProps) {
  const summaryQuery = useAdminDashboardSummary();
  const refreshMutation = useRefreshAdminDashboardSummary();

  if (summaryQuery.isLoading) {
    return <LoadingSpinner data-testid="admin-dashboard-loading" />;
  }
  if (summaryQuery.isError) {
    return (
      <ErrorDisplay
        message={
          (summaryQuery.error as Error)?.message ??
          'Failed to load dashboard summary'
        }
        data-testid="admin-dashboard-error"
      />
    );
  }
  const summary = summaryQuery.data;
  if (!summary) return null;

  return (
    <section
      className="admin-dashboard-overview"
      data-testid="admin-dashboard-overview"
    >
      <div className="admin-dashboard-header">
        <div>
          <h2>Platform Overview</h2>
          <p className="admin-dashboard-meta">
            Updated{' '}
            <time dateTime={summary.generated_at}>
              {new Date(summary.generated_at ?? '').toLocaleString()}
            </time>{' '}
            {summary.cache_hit ? '(cached)' : '(fresh)'}
          </p>
        </div>
        <button
          type="button"
          className="admin-dashboard-refresh"
          onClick={() => refreshMutation.mutate(undefined)}
          disabled={refreshMutation.isPending}
          data-testid="admin-dashboard-refresh"
        >
          {refreshMutation.isPending ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="admin-dashboard-grid">
        <WidgetGuard
          testid="admin-widget-tenants"
          icon="🏢"
          title="Tenants"
          data={summary.tenants}
        >
          {(d) => <TenantsWidget data={d} onOpen={onOpenTenantsTab} />}
        </WidgetGuard>
        <WidgetGuard
          testid="admin-widget-webhooks"
          icon="🔗"
          title="Webhooks"
          data={summary.webhooks}
        >
          {(d) => <WebhooksWidget data={d} />}
        </WidgetGuard>
        <WidgetGuard
          testid="admin-widget-audit"
          icon="🔍"
          title="Audit"
          data={summary.audit}
        >
          {(d) => <AuditWidget data={d} />}
        </WidgetGuard>
        <WidgetGuard
          testid="admin-widget-compliance"
          icon="✅"
          title="Compliance"
          data={summary.compliance}
        >
          {(d) => <ComplianceWidget data={d} />}
        </WidgetGuard>
        <WidgetGuard
          testid="admin-widget-billing"
          icon="💳"
          title="Billing"
          data={summary.billing}
        >
          {(d) => <BillingWidget data={d} />}
        </WidgetGuard>
        <WidgetGuard
          testid="admin-widget-governance"
          icon="📋"
          title="Governance"
          data={summary.governance}
        >
          {(d) => <GovernanceWidget data={d} />}
        </WidgetGuard>
      </div>
    </section>
  );
}

/**
 * Phase 235.5 audit-fix Gap 2 — widget-level error isolation on the
 * SPA side. When the backend returned ``{"widget_error": true}`` for
 * this widget (because that aggregator threw), render a compact
 * fallback card instead of crashing the whole dashboard. The card
 * keeps the widget's testid + title so the dashboard's six-widget
 * grid contract still holds (tests assert all six testids are
 * present regardless of per-widget outcome).
 */
function WidgetGuard<T extends object>({
  testid,
  icon,
  title,
  data,
  children,
}: {
  testid: string;
  icon: string;
  title: string;
  data: T | AdminDashboardWidgetError;
  children: (data: T) => ReactNode;
}) {
  if (isWidgetError(data)) {
    return (
      <article className="admin-widget admin-widget-failed" data-testid={testid}>
        <header className="admin-widget-header">
          <h3>
            {icon} {title}
          </h3>
        </header>
        <p className="admin-widget-error" role="alert">
          This widget failed to load. The aggregator returned an error
          for this subsystem; the rest of the dashboard is unaffected.
          See server logs for the matching{' '}
          <code>admin_dashboard_widget_failed</code> entry.
        </p>
      </article>
    );
  }
  return children(data as T);
}

// ---------------------------------------------------------------------------
// Individual widgets — kept in this single file because each is a thin
// presentational shell over its slice of the aggregate. Splitting into
// six files would create import churn without separating actual
// concerns; if a widget ever grows interaction beyond a static counter
// list it should move into its own file.
// ---------------------------------------------------------------------------

function TenantsWidget({
  data,
  onOpen,
}: {
  data: AdminDashboardTenantsWidget;
  onOpen?: () => void;
}) {
  const stat = (label: string, value: number, danger = false) => (
    <div className={`widget-stat ${danger && value > 0 ? 'widget-stat-danger' : ''}`}>
      <span className="widget-stat-value">{value}</span>
      <span className="widget-stat-label">{label}</span>
    </div>
  );
  return (
    <article className="admin-widget" data-testid="admin-widget-tenants">
      <header className="admin-widget-header">
        <h3>🏢 Tenants</h3>
        {onOpen ? (
          <button
            type="button"
            className="admin-widget-link"
            onClick={onOpen}
            data-testid="admin-widget-tenants-open"
          >
            Manage →
          </button>
        ) : null}
      </header>
      <div className="admin-widget-stats">
        {stat('Total', data.total)}
        {stat('Active', data.active)}
        {stat('Suspended', data.suspended, true)}
        {stat('Deleted', data.deleted ?? 0)}
        {stat('Legal hold', data.legal_hold ?? 0)}
        {stat('Scheduled deletion', data.scheduled_for_deletion ?? 0)}
      </div>
    </article>
  );
}

function WebhooksWidget({ data }: { data: AdminDashboardWebhooksWidget }) {
  const dh = data.delivery_health_last_24h;
  return (
    <article className="admin-widget" data-testid="admin-widget-webhooks">
      <header className="admin-widget-header">
        <h3>🔗 Webhooks</h3>
        <Link to="/webhooks" className="admin-widget-link">
          Open →
        </Link>
      </header>
      <div className="admin-widget-stats">
        <div className="widget-stat">
          <span className="widget-stat-value">{data.total}</span>
          <span className="widget-stat-label">Subscriptions</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.active}</span>
          <span className="widget-stat-label">Active</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.paused}</span>
          <span className="widget-stat-label">Paused</span>
        </div>
      </div>
      <h4 className="admin-widget-subhead">Deliveries (24h)</h4>
      <div className="admin-widget-stats">
        <div className="widget-stat">
          <span className="widget-stat-value">{dh.success}</span>
          <span className="widget-stat-label">Success</span>
        </div>
        <div className={`widget-stat ${dh.failed > 0 ? 'widget-stat-danger' : ''}`}>
          <span className="widget-stat-value">{dh.failed}</span>
          <span className="widget-stat-label">Failed</span>
        </div>
        <div
          className={`widget-stat ${dh.dead_letter > 0 ? 'widget-stat-danger' : ''}`}
        >
          <span className="widget-stat-value">{dh.dead_letter}</span>
          <span className="widget-stat-label">Dead-letter</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{dh.rate_limited}</span>
          <span className="widget-stat-label">Rate-limited</span>
        </div>
      </div>
    </article>
  );
}

function AuditWidget({ data }: { data: AdminDashboardAuditWidget }) {
  return (
    <article className="admin-widget" data-testid="admin-widget-audit">
      <header className="admin-widget-header">
        <h3>🔍 Audit</h3>
        <Link to="/audit" className="admin-widget-link">
          Open →
        </Link>
      </header>
      <div className="admin-widget-stats">
        <div className="widget-stat">
          <span className="widget-stat-value">{data.events_last_24h}</span>
          <span className="widget-stat-label">Events (24h)</span>
        </div>
        <div
          className={`widget-stat ${
            (data.integrity_mismatch_count ?? 0) > 0 ? 'widget-stat-danger' : ''
          }`}
        >
          <span className="widget-stat-value">{data.integrity_mismatch_count}</span>
          <span className="widget-stat-label">Integrity mismatch (24h)</span>
        </div>
      </div>
      <p className="admin-widget-footer">
        Last verified:{' '}
        {data.integrity_verified_at
          ? new Date(data.integrity_verified_at).toLocaleString()
          : 'never'}
      </p>
    </article>
  );
}

function ComplianceWidget({ data }: { data: AdminDashboardComplianceWidget }) {
  return (
    <article className="admin-widget" data-testid="admin-widget-compliance">
      <header className="admin-widget-header">
        <h3>✅ Compliance</h3>
        <Link to="/compliance" className="admin-widget-link">
          Open →
        </Link>
      </header>
      <div className="admin-widget-stats">
        <div className="widget-stat">
          <span className="widget-stat-value">{data.pending}</span>
          <span className="widget-stat-label">Pending</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.running}</span>
          <span className="widget-stat-label">Running</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.succeeded_last_24h}</span>
          <span className="widget-stat-label">Succeeded (24h)</span>
        </div>
        <div
          className={`widget-stat ${
            (data.failed_last_24h ?? 0) > 0 ? 'widget-stat-danger' : ''
          }`}
        >
          <span className="widget-stat-value">{data.failed_last_24h}</span>
          <span className="widget-stat-label">Failed (24h)</span>
        </div>
      </div>
    </article>
  );
}

function BillingWidget({ data }: { data: AdminDashboardBillingWidget }) {
  return (
    <article className="admin-widget" data-testid="admin-widget-billing">
      <header className="admin-widget-header">
        <h3>💳 Billing</h3>
        <Link to="/billing" className="admin-widget-link">
          Open →
        </Link>
      </header>
      <div className="admin-widget-stats">
        <div className="widget-stat">
          <span className="widget-stat-value">{data.active}</span>
          <span className="widget-stat-label">Active</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.trial}</span>
          <span className="widget-stat-label">Trial</span>
        </div>
        <div
          className={`widget-stat ${data.past_due > 0 ? 'widget-stat-danger' : ''}`}
        >
          <span className="widget-stat-value">{data.past_due}</span>
          <span className="widget-stat-label">Past due</span>
        </div>
        <div
          className={`widget-stat ${data.unpaid > 0 ? 'widget-stat-danger' : ''}`}
        >
          <span className="widget-stat-value">{data.unpaid}</span>
          <span className="widget-stat-label">Unpaid</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.canceled}</span>
          <span className="widget-stat-label">Canceled</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">{data.incomplete}</span>
          <span className="widget-stat-label">Incomplete</span>
        </div>
      </div>
    </article>
  );
}

function GovernanceWidget({ data }: { data: AdminDashboardGovernanceWidget }) {
  return (
    <article className="admin-widget" data-testid="admin-widget-governance">
      <header className="admin-widget-header">
        <h3>📋 Governance</h3>
        <Link to="/governance" className="admin-widget-link">
          Open →
        </Link>
      </header>
      <div className="admin-widget-stats">
        <div className="widget-stat">
          <span className="widget-stat-value">{data.open_access_requests}</span>
          <span className="widget-stat-label">Open requests</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">
            {data.approved_access_requests}
          </span>
          <span className="widget-stat-label">Approved</span>
        </div>
        <div className="widget-stat">
          <span className="widget-stat-value">
            {data.rejected_access_requests}
          </span>
          <span className="widget-stat-label">Rejected</span>
        </div>
      </div>
    </article>
  );
}
