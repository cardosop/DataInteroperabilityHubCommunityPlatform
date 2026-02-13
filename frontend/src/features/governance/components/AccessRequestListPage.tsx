/**
 * Access Request List Page
 * Lists access requests with status filter; link to create and to detail
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { AccessRequestStatus } from '../../../shared/types/governance';
import { useAccessRequests } from '../hooks/useGovernance';
import './AccessRequestListPage.css';

const STATUS_OPTIONS: { value: '' | AccessRequestStatus; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'EXPIRED', label: 'Expired' },
  { value: 'REVOKED', label: 'Revoked' },
];

export function AccessRequestListPage() {
  const navigate = useNavigate();
  const [page] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<'' | AccessRequestStatus>('');

  const filters = {
    page,
    page_size: pageSize,
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useAccessRequests(filters);

  const handleRowClick = (id: string) => {
    navigate(`/governance/access-requests/${id}`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading access requests..." />;
  }

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load access requests"
        onRetry={() => refetch()}
      />
    );
  }

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  return (
    <div className="governance-access-request-list-page">
      <div className="governance-list-header">
        <h1>Access Requests</h1>
        <button
          type="button"
          className="btn-primary"
          onClick={() => navigate('/governance/access-requests/create')}
        >
          Create access request
        </button>
      </div>

      <div className="governance-list-filters">
        <label htmlFor="governance-status-filter">Status</label>
        <select
          id="governance-status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter((e.target.value || '') as '' | AccessRequestStatus)}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="No access requests"
          message={
            statusFilter
              ? `No access requests with status "${statusFilter}".`
              : 'No access requests yet. Create one to request access to an asset, dataset, or file.'
          }
          action={{
            label: 'Create access request',
            onClick: () => navigate('/governance/access-requests/create'),
          }}
        />
      ) : (
        <>
          <table className="governance-access-request-table" aria-label="Access requests">
            <thead>
              <tr>
                <th>Reason</th>
                <th>Resource</th>
                <th>Type</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {results.map((ar) => (
                <tr
                  key={ar.id}
                  className="row-link"
                  onClick={() => handleRowClick(ar.id)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRowClick(ar.id)}
                  role="button"
                  tabIndex={0}
                >
                  <td>{ar.reason.length > 60 ? `${ar.reason.slice(0, 60)}…` : ar.reason}</td>
                  <td>
                    {ar.asset && <span>Asset</span>}
                    {ar.dataset && <span>Dataset</span>}
                    {ar.file && <span>File</span>}
                    {!ar.asset && !ar.dataset && !ar.file && '—'}
                  </td>
                  <td>{ar.requested_access_type}</td>
                  <td>
                    <span className={`governance-status-badge ${ar.status}`}>{ar.status}</span>
                  </td>
                  <td>{new Date(ar.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="governance-list-pagination">
            <span className="pagination-info">
              {count} result{count !== 1 ? 's' : ''}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
