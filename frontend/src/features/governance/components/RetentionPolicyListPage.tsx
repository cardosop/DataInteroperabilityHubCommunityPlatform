/**
 * Retention Policy List Page
 * Lists retention policies with filters and pagination
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useRetentionPolicies } from '../hooks/useRetention';
import './RetentionPolicyListPage.css';

export function RetentionPolicyListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [assetIdFilter, setAssetIdFilter] = useState('');
  const [enabledFilter, setEnabledFilter] = useState<boolean | undefined>(undefined);

  const filters = {
    page,
    page_size: pageSize,
    asset_id: assetIdFilter.trim() || undefined,
    enabled: enabledFilter,
  };

  const { data, isLoading, error, refetch } = useRetentionPolicies(filters);

  const handleRowClick = (id: string) => {
    navigate(`/governance/retention/${id}`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading retention policies..." />;
  }

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load retention policies"
        onRetry={() => refetch()}
      />
    );
  }

  const results = data?.results ?? [];
  const count = data?.count ?? 0;
  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="governance-retention-policy-list-page">
      <div className="governance-list-header">
        <h1>Retention Policies</h1>
        <button
          type="button"
          className="btn-primary"
          onClick={() => navigate('/governance/retention/new')}
        >
          Create retention policy
        </button>
      </div>

      <div className="governance-list-filters">
        <div className="filter-group">
          <label htmlFor="asset-id-filter">Asset ID</label>
          <input
            id="asset-id-filter"
            type="text"
            value={assetIdFilter}
            onChange={(e) => {
              setAssetIdFilter(e.target.value);
              setPage(1); // Reset to first page when filter changes
            }}
            placeholder="Filter by asset ID..."
            aria-label="Filter by asset ID"
          />
        </div>
        <div className="filter-group">
          <label htmlFor="enabled-filter">Status</label>
          <select
            id="enabled-filter"
            value={enabledFilter === undefined ? '' : enabledFilter ? 'true' : 'false'}
            onChange={(e) => {
              const value = e.target.value;
              setEnabledFilter(value === '' ? undefined : value === 'true');
              setPage(1); // Reset to first page when filter changes
            }}
            aria-label="Filter by enabled status"
          >
            <option value="">All</option>
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </div>
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="No retention policies"
          message={
            assetIdFilter || enabledFilter !== undefined
              ? 'No retention policies match the current filters.'
              : 'No retention policies yet. Create one to manage data retention for assets, datasets, or files.'
          }
          action={{
            label: 'Create retention policy',
            onClick: () => navigate('/governance/retention/new'),
          }}
        />
      ) : (
        <>
          <table className="governance-retention-policy-table" aria-label="Retention policies">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Resource</th>
                <th>Action</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {results.map((policy) => (
                <tr
                  key={policy.id}
                  className="row-link"
                  onClick={() => handleRowClick(policy.id)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRowClick(policy.id)}
                  role="button"
                  tabIndex={0}
                >
                  <td>{policy.name}</td>
                  <td>{policy.policy_type}</td>
                  <td>
                    {policy.asset && <span>Asset</span>}
                    {policy.dataset && <span>Dataset</span>}
                    {policy.file && <span>File</span>}
                    {!policy.asset && !policy.dataset && !policy.file && '—'}
                  </td>
                  <td>{policy.action}</td>
                  <td>
                    <span
                      className={`governance-status-badge ${policy.enabled ? 'enabled' : 'disabled'}`}
                    >
                      {policy.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                  <td>{new Date(policy.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="governance-list-pagination">
            <span className="pagination-info">
              {count} result{count !== 1 ? 's' : ''} (Page {page} of {totalPages})
            </span>
            <div className="pagination-controls">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
