/**
 * Asset List Page
 * Displays list of assets with filtering and pagination
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { AssetStatus, AssetVisibility } from '../../../shared/types/assets';
import { useAssets } from '../hooks/useAssets';
import './AssetListPage.css';

export function AssetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<AssetStatus | ''>('');
  const [visibilityFilter, setVisibilityFilter] = useState<AssetVisibility | ''>('');

  const filters = {
    page,
    page_size: pageSize,
    search: search || undefined,
    domain: domainFilter || undefined,
    status: statusFilter || undefined,
    visibility: visibilityFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useAssets(filters);

  const handleAssetClick = (assetId: string) => {
    navigate(`/assets/${assetId}`);
  };

  const handleCreateAsset = () => {
    navigate('/assets/create');
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading assets..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load assets" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No assets found"
        message={
          search || domainFilter || statusFilter || visibilityFilter
            ? 'Try adjusting your filters to see more results.'
            : 'Get started by creating your first asset.'
        }
        action={
          !search && !domainFilter && !statusFilter && !visibilityFilter
            ? { label: 'Create Asset', onClick: handleCreateAsset }
            : undefined
        }
      />
    );
  }

  return (
    <div className="asset-list-page">
      <div className="asset-list-header">
        <h1>Assets</h1>
        <button className="btn-primary" onClick={handleCreateAsset} type="button">
          Create Asset
        </button>
      </div>

      <div className="asset-list-filters" role="group" aria-label="Asset filters">
        <label htmlFor="asset-search" className="sr-only">
          Search assets
        </label>
        <input
          id="asset-search"
          type="text"
          placeholder="Search assets..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="filter-input"
          aria-label="Search assets"
        />
        <label htmlFor="asset-domain-filter" className="sr-only">
          Filter by domain
        </label>
        <select
          id="asset-domain-filter"
          value={domainFilter}
          onChange={(e) => {
            setDomainFilter(e.target.value);
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by domain"
        >
          <option value="">All Domains</option>
          {/* Domain options would be populated from backend or extracted from existing assets */}
        </select>
        <label htmlFor="asset-status-filter" className="sr-only">
          Filter by status
        </label>
        <select
          id="asset-status-filter"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as AssetStatus | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="ACTIVE">Active</option>
          <option value="RETIRED">Retired</option>
        </select>
        <label htmlFor="asset-visibility-filter" className="sr-only">
          Filter by visibility
        </label>
        <select
          id="asset-visibility-filter"
          value={visibilityFilter}
          onChange={(e) => {
            setVisibilityFilter(e.target.value as AssetVisibility | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by visibility"
        >
          <option value="">All Visibilities</option>
          <option value="INTERNAL">Internal</option>
          <option value="EXTERNAL">External</option>
          <option value="PUBLIC">Public</option>
        </select>
      </div>

      <div className="asset-list-table">
        <table role="table" aria-label="Assets list">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Key</th>
              <th scope="col">Domain</th>
              <th scope="col">Status</th>
              <th scope="col">Visibility</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((asset) => (
              <tr
                key={asset.id}
                onClick={() => handleAssetClick(asset.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleAssetClick(asset.id);
                  }
                }}
                className="asset-row"
                role="row"
                tabIndex={0}
                aria-label={`Asset ${asset.name}`}
              >
                <td>
                  <strong>{asset.name}</strong>
                  {asset.description && (
                    <div className="asset-description">{asset.description}</div>
                  )}
                </td>
                <td>
                  <code>{asset.key}</code>
                </td>
                <td>{asset.domain || '-'}</td>
                <td>
                  <span
                    className={`status-badge status-${asset.status.toLowerCase()}`}
                    aria-label={`Status: ${asset.status}`}
                  >
                    {asset.status}
                  </span>
                </td>
                <td>
                  <span
                    className={`visibility-badge visibility-${asset.visibility.toLowerCase()}`}
                    aria-label={`Visibility: ${asset.visibility}`}
                  >
                    {asset.visibility}
                  </span>
                </td>
                <td>{new Date(asset.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.total_pages > 1 && (
        <div className="asset-list-pagination">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={!data.has_previous}
            type="button"
          >
            Previous
          </button>
          <span>
            Page {data.page} of {data.total_pages} ({data.count} total)
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={!data.has_next}
            type="button"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
