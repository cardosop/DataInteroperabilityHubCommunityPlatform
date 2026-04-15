/**
 * Role-Specific Dashboard — Phase 224.2
 *
 * Renders role-aware cards and an "Actionable Items" panel directly below the
 * top-level HomePage greeting. Each role sees only the information relevant to
 * their day-to-day work; users with multiple roles see the union.
 */

import { Link } from 'react-router-dom';
import { useAssets } from '../../features/assets/hooks/useAssets';
import { useAuthStore } from '../../features/auth/store/authStore';
import { useAccessRequests } from '../../features/governance/hooks/useGovernance';
import { useAuditEvents } from '../../features/audit/hooks/useAudit';
import { useOrders } from '../../features/marketplace/hooks/useOrders';
import { useEntitlements } from '../../features/marketplace/hooks/useEntitlements';

type RoleFlags = {
  isAdmin: boolean;
  isProvider: boolean;
  isConsumer: boolean;
  isAuditor: boolean;
};

function computeRoleFlags(roles: string[] | undefined): RoleFlags {
  const r = new Set(roles ?? []);
  return {
    isAdmin: r.has('TENANT_ADMIN') || r.has('PLATFORM_ADMIN'),
    isProvider: r.has('DATA_PROVIDER'),
    isConsumer: r.has('DATA_CONSUMER'),
    isAuditor: r.has('AUDITOR'),
  };
}

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function RoleDashboard() {
  const { user } = useAuthStore();
  const flags = computeRoleFlags(user?.roles);
  const anyRole = flags.isAdmin || flags.isProvider || flags.isConsumer || flags.isAuditor;

  // IMPORTANT: hooks must be called unconditionally. Gate network work via
  // React Query's `enabled` option so users without a matching role don't
  // trigger superfluous (or forbidden) requests. `/audit/events/` and
  // `/governance/access-requests/` are role-protected server-side and would
  // otherwise return 403 for consumers/providers, polluting logs + toasts.
  const pendingApprovals = useAccessRequests(
    { status: 'PENDING', page_size: 1 },
    { enabled: !!user && flags.isAdmin },
  );
  const draftAssets = useAssets(
    { status: 'DRAFT', page_size: 1 },
    { enabled: !!user && (flags.isProvider || flags.isAdmin) },
  );
  const myOrders = useOrders(
    { page_size: 1 },
    { enabled: !!user && flags.isConsumer },
  );
  const myEntitlements = useEntitlements(
    { page_size: 1 },
    { enabled: !!user && flags.isConsumer },
  );
  const recentAudit = useAuditEvents(
    { page_size: 5 },
    { enabled: !!user && flags.isAuditor },
  );
  const totalAssets = useAssets({ page_size: 1 }, { enabled: !!user && flags.isAuditor });
  const compliantAssets = useAssets(
    { page_size: 1, compliance_status: 'COMPLIANT' },
    { enabled: !!user && flags.isAuditor },
  );

  if (!user || !anyRole) return null;

  const pendingCount = pendingApprovals.data?.count ?? 0;
  const draftCount = draftAssets.data?.count ?? 0;
  const ordersCount = myOrders.data?.count ?? 0;
  const entCount = myEntitlements.data?.count ?? 0;
  const auditItems = recentAudit.data?.results ?? [];

  const compliancePct =
    totalAssets.data?.count && totalAssets.data.count > 0
      ? Math.round(((compliantAssets.data?.count ?? 0) / totalAssets.data.count) * 100)
      : null;

  const actionable: Array<{ key: string; label: string; to: string }> = [];
  if (flags.isAdmin && pendingCount > 0) {
    actionable.push({
      key: 'pending-approvals',
      label: `${pendingCount} pending access request${pendingCount === 1 ? '' : 's'} awaiting your review`,
      to: '/governance',
    });
  }
  if (flags.isProvider && draftCount > 0) {
    actionable.push({
      key: 'draft-assets',
      label: `${draftCount} draft asset${draftCount === 1 ? '' : 's'} need${draftCount === 1 ? 's' : ''} a contract before activation`,
      to: '/assets?status=DRAFT',
    });
  }

  return (
    <div className="role-dashboard" data-testid="role-dashboard">
      <h2>For You</h2>
      <div className="role-dashboard-cards">
        {flags.isAdmin && (
          <Link
            to="/governance"
            className="role-card"
            data-testid="role-card-pending-approvals"
          >
            <span className="role-card__value">{pendingCount}</span>
            <span className="role-card__label">Pending Approvals</span>
          </Link>
        )}

        {flags.isProvider && (
          <Link
            to="/assets?status=DRAFT"
            className="role-card"
            data-testid="role-card-my-draft-assets"
          >
            <span className="role-card__value">{draftCount}</span>
            <span className="role-card__label">My Draft Assets</span>
            <span className="role-card__cta">Activate →</span>
          </Link>
        )}

        {flags.isConsumer && (
          <>
            <Link
              to="/marketplace/orders"
              className="role-card"
              data-testid="role-card-my-orders"
            >
              <span className="role-card__value">{ordersCount}</span>
              <span className="role-card__label">My Orders</span>
            </Link>
            <Link
              to="/marketplace/entitlements"
              className="role-card"
              data-testid="role-card-my-entitlements"
            >
              <span className="role-card__value">{entCount}</span>
              <span className="role-card__label">My Entitlements</span>
            </Link>
          </>
        )}

        {flags.isAuditor && (
          <>
            <div className="role-card role-card--wide" data-testid="role-card-recent-audit">
              <span className="role-card__label">Recent Audit Events</span>
              {auditItems.length === 0 ? (
                <span className="role-card__empty">No recent events</span>
              ) : (
                <ul className="role-card__list">
                  {auditItems.map((e) => (
                    <li key={e.id}>
                      <Link to={`/audit/${e.id}`}>
                        <span className="audit-action">{e.action}</span>
                        <span className="audit-meta">
                          {e.resource_type} · {formatTs(e.timestamp)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <Link
              to="/compliance"
              className="role-card"
              data-testid="role-card-compliance-summary"
            >
              <span className="role-card__value">
                {compliancePct !== null ? `${compliancePct}%` : '—'}
              </span>
              <span className="role-card__label">Compliance Summary</span>
            </Link>
          </>
        )}
      </div>

      {actionable.length > 0 && (
        <section className="actionable-items" data-testid="actionable-items">
          <h3>Actionable Items</h3>
          <ul className="actionable-items__list">
            {actionable.map((item) => (
              <li key={item.key} data-testid={`actionable-item-${item.key}`}>
                <Link to={item.to}>{item.label}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
