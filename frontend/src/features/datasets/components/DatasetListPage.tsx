/**
 * Dataset List Page
 */

import { useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { useDatasets } from '../hooks/useDatasets';
import './DatasetListPage.css';
import { Button } from '../../../shared/components/Button';

export function DatasetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [assetIdFilter, setAssetIdFilter] = useState('');
  // PR 5.3: debounce the asset-id text filter; input stays controlled by raw state.
  const debouncedAssetId = useDebouncedValue(assetIdFilter, 300);
  const filters = {
    page,
    page_size: 50,
    ordering: '-created_at',
    asset_id: debouncedAssetId.trim() || undefined,
  };
  const { data, isLoading, error, refetch } = useDatasets(filters);
  const handleCreateDataset = () => navigate('/datasets/create');
  const hasFilters = !!debouncedAssetId.trim();

  // Track B structural inversion: header + filter bar render unconditionally
  // above isLoading/error/empty guards so the filter input DOM is stable
  // across query state transitions (defense-in-depth alongside keepPreviousData).
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay error={error} title="Failed to load datasets" onRetry={() => refetch()} />
    );
  } else if (!data || data.results.length === 0) {
    mainContent = (
      <EmptyState
        data-testid="dataset-list-empty-state"
        title="No datasets found"
        message={
          hasFilters
            ? 'No datasets match the current filter. Try adjusting or clear the filter.'
            : 'Get started by creating your first dataset.'
        }
        action={
          hasFilters
            ? {
                label: 'Clear filter',
                onClick: () => {
                  setAssetIdFilter('');
                  setPage(1);
                },
              }
            : { label: 'Create Dataset', onClick: handleCreateDataset }
        }
      />
    );
  } else {
    mainContent = (
      <>
        <div className="dataset-list-table">
          <table role="table" aria-label="Datasets list">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Asset</th>
                <th scope="col">Format</th>
                <th scope="col">Size</th>
                <th scope="col">Rows</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((dataset) => {
                const assetId = dataset.asset_id ?? dataset.asset;
                return (
                  <tr
                    key={dataset.id}
                    onClick={() => navigate(`/datasets/${dataset.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        navigate(`/datasets/${dataset.id}`);
                      }
                    }}
                    className="dataset-row"
                    role="row"
                    tabIndex={0}
                    aria-label={`Dataset ${dataset.name}`}
                  >
                    <td>
                      <strong>{dataset.name}</strong>
                    </td>
                    <td>
                      {assetId ? (
                        <Link
                          to={`/assets/${assetId}`}
                          onClick={(e) => e.stopPropagation()}
                          className="dataset-list-asset-link"
                        >
                          {dataset.asset_name ?? 'View asset'}
                        </Link>
                      ) : (
                        <span className="dataset-list-no-asset">—</span>
                      )}
                    </td>
                    <td>{dataset.format}</td>
                    <td>{(dataset.size_bytes / 1024).toFixed(2)} KB</td>
                    <td>{dataset.row_count?.toLocaleString() || '-'}</td>
                    <td>{new Date(dataset.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {data.total_pages > 1 && (
          <div className="dataset-list-pagination">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={!data.has_previous}>
              Previous
            </button>
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              disabled={!data.has_next}
            >
              Next
            </button>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="dataset-list-page" data-testid="dataset-list-page">
      <div className="dataset-list-header">
        <h1>Datasets</h1>
        <Button variant="primary" onClick={handleCreateDataset}>
          Create Dataset
        </Button>
      </div>
      <div className="dataset-list-filters" data-testid="dataset-list-filters">
        <label htmlFor="dataset-asset-id-filter" className="sr-only">
          Filter by Asset ID
        </label>
        <input
          id="dataset-asset-id-filter"
          type="text"
          placeholder="Asset ID (optional)"
          value={assetIdFilter}
          onChange={(e) => {
            setAssetIdFilter(e.target.value);
            setPage(1);
          }}
          className="dataset-list-filter-input"
          aria-label="Filter by Asset ID"
        />
      </div>
      {mainContent}
    </div>
  );
}
