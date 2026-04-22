/**
 * Virtual Dataset List Page
 * Displays list of virtual datasets with filtering and pagination
 */

import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useVirtualDatasets } from '../hooks/useVirtualization';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { VirtualDatasetStatus, QueryType } from '../../../shared/types/virtualization';
import './VirtualDatasetListPage.css';
import { Button } from '../../../shared/components/Button';

export function VirtualDatasetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<VirtualDatasetStatus | ''>('');
  const [queryTypeFilter, setQueryTypeFilter] = useState<QueryType | ''>('');
  // PR 5.3: debounce the search input.
  const debouncedSearch = useDebouncedValue(search, 300);

  const filters = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    status: statusFilter || undefined,
    query_type: queryTypeFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useVirtualDatasets(filters);

  const handleDatasetClick = (datasetId: string) => {
    navigate(`/virtualization/${datasetId}`);
  };

  const handleCreateDataset = () => {
    navigate('/virtualization/create');
  };

  const hasActiveFilter = !!(debouncedSearch || statusFilter || queryTypeFilter);

  // Track B structural inversion: header + filter bar render unconditionally.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay
        error={error}
        title="Failed to load virtual datasets"
        onRetry={() => refetch()}
      />
    );
  } else if (!data || data.results.length === 0) {
    mainContent = (
      <EmptyState
        title="No virtual datasets found"
        message={
          hasActiveFilter
            ? 'Try adjusting your filters to see more results.'
            : 'Get started by creating your first virtual dataset.'
        }
        action={!hasActiveFilter ? { label: 'Create Dataset', onClick: handleCreateDataset } : undefined}
      />
    );
  } else {
    mainContent = (
      <>
        <div className="virtual-dataset-list-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Query Type</th>
                <th>Status</th>
                <th>Version</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((dataset) => (
                <tr
                  key={dataset.id}
                  onClick={() => handleDatasetClick(dataset.id)}
                  className="clickable-row"
                >
                  <td>
                    <strong>{dataset.name}</strong>
                  </td>
                  <td>
                    {dataset.description || <span className="text-muted">No description</span>}
                  </td>
                  <td>
                    <span className="query-type-badge">{dataset.query_type}</span>
                  </td>
                  <td>
                    <span className={`status-badge status-${dataset.status.toLowerCase()}`}>
                      {dataset.status}
                    </span>
                  </td>
                  <td>{dataset.version}</td>
                  <td>{new Date(dataset.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="btn-link"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDatasetClick(dataset.id);
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
          <div className="virtual-dataset-list-pagination">
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span>
              Page {page} of {Math.ceil(data.count / pageSize)}
            </span>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => p + 1)}
              disabled={!data.has_next}
            >
              Next
            </Button>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="virtual-dataset-list-page">
      <div className="virtual-dataset-list-header">
        <h1>Virtual Datasets</h1>
        <Button variant="primary" onClick={handleCreateDataset}>
          Create Dataset
        </Button>
      </div>

      <div className="virtual-dataset-list-filters">
        <input
          type="text"
          placeholder="Search datasets..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="filter-input"
          aria-label="Search virtual datasets"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as VirtualDatasetStatus | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value={VirtualDatasetStatus.DRAFT}>Draft</option>
          <option value={VirtualDatasetStatus.ACTIVE}>Active</option>
          <option value={VirtualDatasetStatus.INACTIVE}>Inactive</option>
          <option value={VirtualDatasetStatus.ARCHIVED}>Archived</option>
        </select>
        <select
          value={queryTypeFilter}
          onChange={(e) => {
            setQueryTypeFilter(e.target.value as QueryType | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by query type"
        >
          <option value="">All Query Types</option>
          <option value={QueryType.SQL}>SQL</option>
          <option value={QueryType.SPARQL}>SPARQL</option>
          <option value={QueryType.FEDERATED}>Federated</option>
          <option value={QueryType.GRAPHQL}>GraphQL</option>
          <option value={QueryType.REST}>REST</option>
        </select>
      </div>

      {mainContent}
    </div>
  );
}
