/**
 * Marketplace Mapping List Page
 * View marketplace mappings
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMarketplaceMappings } from '../hooks/useMarketplaceMappings';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import './MarketplaceMappingListPage.css';

export function MarketplaceMappingListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);

  const filters = {
    page,
    page_size: pageSize,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useMarketplaceMappings(filters);

  const handleMappingClick = (mappingId: string) => {
    navigate(`/integrations/mappings/${mappingId}`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading mappings..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load mappings" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No mappings found"
        message="Mappings are created automatically when assets are synced to external marketplaces."
      />
    );
  }

  return (
    <div className="mapping-list-page">
      <div className="mapping-list-header">
        <h1>Marketplace Mappings</h1>
      </div>

      <div className="mapping-list-table">
        <table>
          <thead>
            <tr>
              <th>Connection</th>
              <th>Hub Asset ID</th>
              <th>External Listing ID</th>
              <th>Last Synced</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((mapping) => (
              <tr
                key={mapping.id}
                onClick={() => handleMappingClick(mapping.id)}
                className="mapping-row"
              >
                <td>{mapping.connection.name}</td>
                <td className="mapping-id">{mapping.hub_asset_id}</td>
                <td className="mapping-id">{mapping.external_listing_id}</td>
                <td>
                  {mapping.last_synced_at
                    ? new Date(mapping.last_synced_at).toLocaleDateString()
                    : 'Never'}
                </td>
                <td>
                  <button
                    className="btn-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleMappingClick(mapping.id);
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
        <div className="mapping-list-pagination">
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
