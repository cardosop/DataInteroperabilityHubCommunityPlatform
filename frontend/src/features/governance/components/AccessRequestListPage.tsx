/**
 * Access Request List Page
 * Lists access requests with status filter; link to create and to detail.
 * Supports bulk approve/reject for TENANT_ADMIN/PLATFORM_ADMIN (223.3.4).
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BulkActionBar } from '../../../shared/components/BulkActionBar';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useBulkSelection } from '../../../shared/hooks/useBulkSelection';
import { exportToCSV } from '../../../shared/utils/exportUtils';
import type { AccessRequestStatus } from '../../../shared/types/governance';
import { useAuthStore } from '../../auth/store/authStore';
import {
  useAccessRequests,
  useBulkApproveAccessRequests,
  useBulkRejectAccessRequests,
} from '../hooks/useGovernance';
import './AccessRequestListPage.css';
import { Button } from '../../../shared/components/Button';

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
  const user = useAuthStore((s) => s.user);
  const isAdmin =
    (user?.roles ?? []).some((r) => r === 'TENANT_ADMIN' || r === 'PLATFORM_ADMIN') ||
    !!user?.is_platform_admin;

  const bulkApprove = useBulkApproveAccessRequests();
  const bulkReject = useBulkRejectAccessRequests();

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  // Only PENDING rows are bulk-actionable — approving a REJECTED / APPROVED
  // request is a business-rule error, and the checkbox would mislead.
  const selection = useBulkSelection({
    allIds: results.map((ar) => ar.id),
    isSelectable: (id) => results.find((r) => r.id === id)?.status === 'PENDING',
  });

  const handleRowClick = (id: string) => {
    navigate(`/governance/access-requests/${id}`);
  };

  const handleBulkApprove = async () => {
    if (selection.selectedIds.length === 0) return;
    try {
      await bulkApprove.mutateAsync({ ids: selection.selectedIds });
    } finally {
      selection.deselectAll();
      refetch();
    }
  };

  const handleBulkReject = async () => {
    if (selection.selectedIds.length === 0) return;
    const reason = window.prompt('Reason for rejection (required):');
    if (!reason) return;
    try {
      await bulkReject.mutateAsync({ ids: selection.selectedIds, reason });
    } finally {
      selection.deselectAll();
      refetch();
    }
  };

  if (isLoading) {
    return <ListPageSkeleton />;
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

  return (
    <div className="governance-access-request-list-page">
      <div className="governance-list-header">
        <h1>Access Requests</h1>
        <div className="governance-list-header-actions" style={{ display: 'flex', gap: '0.5rem' }}>
          <Button
            variant="secondary"
            disabled={results.length === 0}
            onClick={() =>
              exportToCSV(
                results as unknown as Array<Record<string, unknown>>,
                'access-requests',
                {
                  columns: [
                    { key: 'id', label: 'ID' },
                    { key: 'status', label: 'Status' },
                    { key: 'requested_access_type', label: 'Type' },
                    { key: 'reason', label: 'Reason' },
                    { key: 'asset', label: 'Asset' },
                    { key: 'dataset', label: 'Dataset' },
                    { key: 'file', label: 'File' },
                    { key: 'created_at', label: 'Created' },
                  ],
                },
              )
            }
            data-testid="access-requests-export-csv"
          >
            Export CSV
          </Button>
          <Button
 variant="primary"
 onClick={() => navigate('/governance/access-requests/create')}>
            Create access request
          </Button>
        </div>
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
                {isAdmin && (
                  <th style={{ width: '2.5rem' }}>
                    <input
                      type="checkbox"
                      aria-label="Select all pending rows"
                      checked={selection.isAllSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = selection.isIndeterminate;
                      }}
                      onChange={() => selection.toggleAll()}
                      data-testid="access-request-select-all"
                    />
                  </th>
                )}
                <th>Reason</th>
                <th>Resource</th>
                <th>Type</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {results.map((ar) => {
                const canSelect = ar.status === 'PENDING';
                return (
                  <tr
                    key={ar.id}
                    className="row-link"
                    onClick={(e) => {
                      if ((e.target as HTMLElement).tagName === 'INPUT') return;
                      handleRowClick(ar.id);
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && handleRowClick(ar.id)}
                    role="button"
                    tabIndex={0}
                  >
                    {isAdmin && (
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Select request ${ar.id}`}
                          checked={selection.isSelected(ar.id)}
                          disabled={!canSelect}
                          onChange={() => selection.toggle(ar.id)}
                          onClick={(e) => e.stopPropagation()}
                          data-testid={`access-request-select-${ar.id}`}
                        />
                      </td>
                    )}
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
                );
              })}
            </tbody>
          </table>
          <div className="governance-list-pagination">
            <span className="pagination-info">
              {count} result{count !== 1 ? 's' : ''}
            </span>
          </div>
        </>
      )}

      {isAdmin && (
        <BulkActionBar
          selectedCount={selection.selectedCount}
          onDeselectAll={selection.deselectAll}
          description="Only PENDING requests can be bulk-acted."
          actions={[
            {
              label: 'Approve',
              variant: 'primary',
              onClick: handleBulkApprove,
              disabled: bulkApprove.isPending,
              'data-testid': 'bulk-approve',
            },
            {
              label: 'Reject',
              variant: 'danger',
              onClick: handleBulkReject,
              disabled: bulkReject.isPending,
              'data-testid': 'bulk-reject',
            },
          ]}
        />
      )}
    </div>
  );
}
