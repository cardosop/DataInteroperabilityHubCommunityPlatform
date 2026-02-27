/**
 * Mesh Domain List Page
 * Displays list of mesh domains with filtering and pagination
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMeshDomains } from '../hooks/useMesh';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { DomainStatus } from '../../../shared/types/mesh';
import './MeshDomainListPage.css';

export function MeshDomainListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<DomainStatus | ''>('');

  const filters = {
    page,
    page_size: pageSize,
    search: search || undefined,
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

  if (isLoading) {
    return <LoadingSpinner message="Loading mesh domains..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load mesh domains" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <div className="mesh-domain-list-page">
        <div className="mesh-domain-list-header">
          <h1>Mesh Domains</h1>
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
        </div>
        <EmptyState
          title="No mesh domains found"
          message={search || statusFilter
            ? "Try adjusting your filters to see more results."
            : "Get started by creating your first mesh domain."}
          action={!search && !statusFilter
            ? { label: 'Create Domain', onClick: handleCreateDomain }
            : undefined}
        />
      </div>
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
          <button className="btn-primary" onClick={handleCreateDomain} type="button">
            Create Domain
          </button>
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
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as DomainStatus | '');
            setPage(1);
          }}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={DomainStatus.ACTIVE}>Active</option>
          <option value={DomainStatus.INACTIVE}>Inactive</option>
          <option value={DomainStatus.ARCHIVED}>Archived</option>
        </select>
      </div>

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
              <tr key={domain.id} onClick={() => handleDomainClick(domain.id)} className="clickable-row">
                <td>
                  <strong>{domain.name}</strong>
                </td>
                <td>{domain.description || <span className="text-muted">No description</span>}</td>
                <td>
                  <span className={`status-badge status-${domain.status.toLowerCase()}`}>
                    {domain.status}
                  </span>
                </td>
                <td>{domain.owner_email || <span className="text-muted">No owner</span>}</td>
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
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            type="button"
          >
            Previous
          </button>
          <span>
            Page {page} of {Math.ceil(data.count / pageSize)}
          </span>
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => p + 1)}
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
