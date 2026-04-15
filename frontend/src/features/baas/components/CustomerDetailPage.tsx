/**
 * Customer Detail Page — Phase 116C.2
 * Shows per-key usage and billing history for a customer.
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useAPIKeys, useBillingReports } from '../hooks/useBaaS';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { Button } from '../../../shared/components/Button';
import { statusBadgeClass } from './billingUtils';

export function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>();
  const navigate = useNavigate();
  const { data: apiKeysData, isLoading: keysLoading, error: keysError } = useAPIKeys();
  const { data: reportsData, isLoading: reportsLoading, error: reportsError } = useBillingReports({
    customer_id: customerId,
  });

  const customerKeys = (apiKeysData?.results || []).filter(
    (k) => k.customer_id === customerId
  );
  const customerName = customerKeys[0]?.customer_name || customerId;
  const customerEmail = customerKeys[0]?.customer_email || '';

  if (keysLoading || reportsLoading) return <LoadingSpinner message="Loading customer details..." />;
  if (keysError) return <ErrorDisplay error={keysError} title="Failed to load API keys" />;

  return (
    <div className="customer-detail-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'BaaS', href: '/baas' },
          { label: customerName || 'Customer' },
        ]}
      />
      <Button variant="secondary" onClick={() => navigate('/settings/baas')}>
        Back
      </Button>

      <div className="customer-header">
        <h2>{customerName}</h2>
        <p className="customer-meta">
          <code>{customerId}</code>
          {customerEmail && <span> · {customerEmail}</span>}
        </p>
      </div>

      {/* API Keys */}
      <section className="customer-section">
        <h3>API Keys ({customerKeys.length})</h3>
        {customerKeys.length === 0 ? (
          <EmptyState title="No API keys" message="No API keys found for this customer." />
        ) : (
          <table className="billing-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Tier</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {customerKeys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td><span className={`tier-badge tier-${key.tier.toLowerCase()}`}>{key.tier}</span></td>
                  <td>{key.revoked_at ? <span className="revoked-badge">Revoked</span> : 'Active'}</td>
                  <td>{new Date(key.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Billing History */}
      <section className="customer-section">
        <h3>Billing History</h3>
        {reportsError && <ErrorDisplay error={reportsError} title="Failed to load reports" />}
        {reportsData && reportsData.results.length === 0 && (
          <EmptyState title="No billing reports" message="No reports generated for this customer yet." />
        )}
        {reportsData && reportsData.results.length > 0 && (
          <table className="billing-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Requests</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {reportsData.results.map((report) => (
                <tr
                  key={report.id}
                  className="clickable-row"
                  onClick={() => navigate(`/settings/baas/billing-reports/${report.id}`)}
                >
                  <td>
                    {new Date(report.period_start).toLocaleDateString()} –{' '}
                    {new Date(report.period_end).toLocaleDateString()}
                  </td>
                  <td>{report.total_requests.toLocaleString()}</td>
                  <td>{report.total_amount} {report.currency}</td>
                  <td><span className={statusBadgeClass(report.status)}>{report.status}</span></td>
                  <td>{new Date(report.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
