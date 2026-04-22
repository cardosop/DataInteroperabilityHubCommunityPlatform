/**
 * Retention Policy List Page
 * Lists retention policies with filters and pagination
 */

import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { useRetentionPolicies } from '../hooks/useRetention';
import './RetentionPolicyListPage.css';
import { Button } from '../../../shared/components/Button';

export function RetentionPolicyListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [assetIdFilter, setAssetIdFilter] = useState('');
  const [enabledFilter, setEnabledFilter] = useState<boolean | undefined>(undefined);
  // PR 5.3: debounce the asset-id text filter.
  const debouncedAssetId = useDebouncedValue(assetIdFilter, 300);

  const filters = {
    page,
    page_size: pageSize,
    asset_id: debouncedAssetId.trim() || undefined,
    enabled: enabledFilter,
  };

  const { data, isLoading, error, refetch } = useRetentionPolicies(filters);

  const handleRowClick = (id: string) => {
    navigate(`/governance/retention/${id}`);
  };

  const results = data?.results ?? [];
  const count = data?.count ?? 0;
  const totalPages = data?.total_pages ?? 1;
  const hasActiveFilter = !!debouncedAssetId.trim() || enabledFilter !== undefined;

  // Track B structural inversion: header + filter bar render unconditionally.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay
        error={error}
        title="Failed to load retention policies"
        onRetry={() => refetch()}
      />
    );
  } else if (results.length === 0) {
    mainContent = (
      <EmptyState
        title="No retention policies"
        message={
          hasActiveFilter
            ? 'No retention policies match the current filters.'
            : 'No retention policies yet. Create one to manage data retention for assets, datasets, or files.'
        }
        action={{
          label: 'Create retention policy',
          onClick: () => navigate('/governance/retention/new'),
        }}
      />
    );
  } else {
    mainContent = (
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
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="governance-retention-policy-list-page">
      <div className="governance-list-header">
        <h1>Retention Policies</h1>
        <Button variant="primary" onClick={() => navigate('/governance/retention/new')}>
          Create retention policy
        </Button>
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
              setPage(1);
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
              setPage(1);
            }}
            aria-label="Filter by enabled status"
          >
            <option value="">All</option>
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </div>
      </div>

      {mainContent}
    </div>
  );
}
