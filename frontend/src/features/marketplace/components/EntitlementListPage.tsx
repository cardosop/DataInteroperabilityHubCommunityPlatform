/**
 * Entitlement List Page
 * View all entitlements
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEntitlements } from '../hooks/useEntitlements';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { EntitlementStatus } from '../../../shared/types/marketplace';
import './EntitlementListPage.css';

export function EntitlementListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<EntitlementStatus | ''>('');

  const filters = {
    page,
    page_size: pageSize,
    status: statusFilter || undefined,
    ordering: '-granted_at',
  };

  const { data, isLoading, error, refetch } = useEntitlements(filters);

  const handleEntitlementClick = (entitlementId: string) => {
    navigate(`/marketplace/entitlements/${entitlementId}`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading entitlements..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load entitlements" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No entitlements found"
        message={statusFilter
          ? "Try adjusting your filters to see more results."
          : "You don't have any entitlements yet."}
      />
    );
  }

  return (
    <div className="entitlement-list-page">
      <div className="entitlement-list-header">
        <h1>Entitlements</h1>
      </div>

      <div className="entitlement-list-filters">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as EntitlementStatus | '');
            setPage(1);
          }}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={EntitlementStatus.ACTIVE}>Active</option>
          <option value={EntitlementStatus.REVOKED}>Revoked</option>
          <option value={EntitlementStatus.EXPIRED}>Expired</option>
        </select>
      </div>

      <div className="entitlement-list-table">
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Listing</th>
              <th>Status</th>
              <th>Granted</th>
              <th>Expires</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((entitlement) => (
              <tr
                key={entitlement.id}
                onClick={() => handleEntitlementClick(entitlement.id)}
                className="entitlement-row"
              >
                <td>{entitlement.asset_name || entitlement.asset}</td>
                <td>{entitlement.listing_title || entitlement.listing}</td>
                <td>
                  <span className={`entitlement-status entitlement-status-${entitlement.status.toLowerCase()}`}>
                    {entitlement.status}
                  </span>
                </td>
                <td>{new Date(entitlement.granted_at).toLocaleDateString()}</td>
                <td>
                  {entitlement.expires_at
                    ? new Date(entitlement.expires_at).toLocaleDateString()
                    : 'Never'}
                </td>
                <td>
                  <button
                    className="btn-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEntitlementClick(entitlement.id);
                    }}
                    type="button"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.count > pageSize && (
        <div className="entitlement-list-pagination">
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            type="button"
          >
            Previous
          </button>
          <span className="pagination-info">
            Page {page} of {Math.ceil(data.count / pageSize)}
          </span>
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(data.count / pageSize)}
            type="button"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
