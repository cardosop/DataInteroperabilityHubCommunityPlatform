/**
 * Billing Report List Page — Phase 116C.3
 * Lists all billing reports with status filter.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useBillingReports } from '../hooks/useBaaS';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { BillingReportStatus } from '../../../shared/types/baas';
import { statusBadgeClass } from './billingUtils';

export function BillingReportListPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const { data, isLoading, error } = useBillingReports(
    statusFilter ? { status: statusFilter } : {}
  );

  if (isLoading) return <LoadingSpinner message="Loading billing reports..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load billing reports" />;

  const reports = data?.results || [];

  return (
    <div className="billing-report-list-page">
      <div className="section-header">
        <h2>Billing Reports</h2>
        <div className="filter-bar">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All Statuses</option>
            <option value={BillingReportStatus.DRAFT}>Draft</option>
            <option value={BillingReportStatus.FINALIZED}>Finalized</option>
            <option value={BillingReportStatus.SENT}>Sent</option>
            <option value={BillingReportStatus.VOID}>Void</option>
          </select>
        </div>
      </div>

      {reports.length === 0 ? (
        <EmptyState
          title="No billing reports"
          message="Generate reports from the management command or API."
        />
      ) : (
        <table className="billing-table">
          <thead>
            <tr>
              <th>Customer</th>
              <th>Period</th>
              <th>Requests</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((report) => (
              <tr
                key={report.id}
                className="clickable-row"
                onClick={() => navigate(`/settings/baas/billing-reports/${report.id}`)}
              >
                <td>
                  <div className="customer-name">{report.customer_name || report.customer_id}</div>
                  <div className="customer-id-sub">{report.customer_id}</div>
                </td>
                <td>
                  {new Date(report.period_start).toLocaleDateString()} –{' '}
                  {new Date(report.period_end).toLocaleDateString()}
                </td>
                <td>{report.total_requests.toLocaleString()}</td>
                <td className="amount-cell">{report.total_amount} {report.currency}</td>
                <td><span className={statusBadgeClass(report.status)}>{report.status}</span></td>
                <td>{new Date(report.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
