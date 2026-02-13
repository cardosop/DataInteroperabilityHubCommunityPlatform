/**
 * Marketplace Connection List Page
 * View and manage marketplace connections
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMarketplaceConnections } from '../hooks/useMarketplaceConnections';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import './MarketplaceConnectionListPage.css';

export function MarketplaceConnectionListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);

  const filters = {
    page,
    page_size: pageSize,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useMarketplaceConnections(filters);

  const handleConnectionClick = (connectionId: string) => {
    navigate(`/integrations/connections/${connectionId}`);
  };

  const handleCreateConnection = () => {
    navigate('/integrations/connections/create');
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading connections..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load connections" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No connections found"
        message="Get started by creating your first marketplace connection."
        action={{ label: 'Create Connection', onClick: handleCreateConnection }}
      />
    );
  }

  return (
    <div className="connection-list-page">
      <div className="connection-list-header">
        <h1>Marketplace Connections</h1>
        <button className="btn-primary" onClick={handleCreateConnection} type="button">
          Create Connection
        </button>
      </div>

      <div className="connection-list-grid">
        {data.results.map((connection) => (
          <div
            key={connection.id}
            className="connection-card"
            onClick={() => handleConnectionClick(connection.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleConnectionClick(connection.id);
              }
            }}
          >
            <div className="connection-card-header">
              <h3>{connection.name}</h3>
              <span className={`connection-status ${connection.is_active ? 'active' : 'inactive'}`}>
                {connection.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="connection-type">{connection.marketplace_type}</p>
            {connection.last_sync_at && (
              <p className="connection-last-sync">
                Last sync: {new Date(connection.last_sync_at).toLocaleDateString()}
              </p>
            )}
          </div>
        ))}
      </div>

      {data.count > pageSize && (
        <div className="connection-list-pagination">
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
