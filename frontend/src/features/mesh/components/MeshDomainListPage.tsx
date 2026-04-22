/**
 * Mesh Domain List Page
 * Displays list of mesh domains with filtering and pagination
 */

import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMeshDomains } from '../hooks/useMesh';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { DomainStatus } from '../../../shared/types/mesh';
import './MeshDomainListPage.css';
import { Button } from '../../../shared/components/Button';

export function MeshDomainListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<DomainStatus | ''>('');
  // PR 5.3: debounce the free-text search input.
  const debouncedSearch = useDebouncedValue(search, 300);

  const filters = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    status: statusFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useMeshDomains(filters);

  const handleDomainClick = (domainId: string) => {
    navigate(`/mesh/${domainId}`);
  };

  const handleCreateDomain = () => {
    navigate('/mesh/create');
  };

  const handleTopologyClick = () => {
    navigate('/mesh/topology');
  };

  const hasActiveFilter = !!(debouncedSearch || statusFilter);

  // Track B structural inversion: header + filter bar render unconditionally.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay
        error={error}
        title="Failed to load mesh domains"
        onRetry={() => refetch()}
      />
    );
  } else if (!data || data.results.length === 0) {
    mainContent = (
      <EmptyState
        title="No mesh domains found"
        message={
          hasActiveFilter
            ? 'Try adjusting your filters to see more results.'
            : 'Get started by creating your first mesh domain.'
        }
        action={!hasActiveFilter ? { label: 'Create Domain', onClick: handleCreateDomain } : undefined}
      />
    );
  } else {
    mainContent = (
      <>
        <div className="mesh-domain-list-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Status</th>
                <th>Owner</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((domain) => (
                <tr
                  key={domain.id}
                  onClick={() => handleDomainClick(domain.id)}
                  className="clickable-row"
                >
                  <td>
                    <strong>{domain.name}</strong>
                  </td>
                  <td>
                    {domain.description || <span className="text-muted">No description</span>}
                  </td>
                  <td>
                    <span className={`status-badge status-${domain.status.toLowerCase()}`}>
                      {domain.status}
                    </span>
                  </td>
                  <td>
                    {domain.owner_email || <span className="text-muted">No owner</span>}
                  </td>
                  <td>{new Date(domain.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="btn-link"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDomainClick(domain.id);
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
          <div className="mesh-domain-list-pagination">
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
    <div className="mesh-domain-list-page">
      <div className="mesh-domain-list-header">
        <h1>Mesh Domains</h1>
        <div className="mesh-domain-list-header-actions">
          <a
            href="/mesh/topology"
            onClick={(e) => {
              e.preventDefault();
              handleTopologyClick();
            }}
            className="btn-secondary"
          >
            Topology
          </a>
          <Button variant="primary" onClick={handleCreateDomain}>
            Create Domain
          </Button>
        </div>
      </div>

      <div className="mesh-domain-list-filters">
        <input
          type="text"
          placeholder="Search domains..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="filter-input"
          aria-label="Search mesh domains"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as DomainStatus | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value={DomainStatus.ACTIVE}>Active</option>
          <option value={DomainStatus.INACTIVE}>Inactive</option>
          <option value={DomainStatus.ARCHIVED}>Archived</option>
        </select>
      </div>

      {mainContent}
    </div>
  );
}
