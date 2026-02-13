/**
 * Dataset List Page
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useDatasets } from '../hooks/useDatasets';
import './DatasetListPage.css';

export function DatasetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useDatasets({
    page,
    page_size: 50,
    ordering: '-created_at',
  });

  if (isLoading) return <LoadingSpinner message="Loading datasets..." />;
  if (error)
    return <ErrorDisplay error={error} title="Failed to load datasets" onRetry={() => refetch()} />;
  if (!data || data.results.length === 0) {
    return (
      <EmptyState title="No datasets found" message="Get started by creating your first dataset." />
    );
  }

  return (
    <div className="dataset-list-page">
      <div className="dataset-list-header">
        <h1>Datasets</h1>
      </div>
      <div className="dataset-list-table">
        <table role="table" aria-label="Datasets list">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Format</th>
              <th scope="col">Size</th>
              <th scope="col">Rows</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((dataset) => (
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
                <td>{dataset.format}</td>
                <td>{(dataset.size_bytes / 1024).toFixed(2)} KB</td>
                <td>{dataset.row_count?.toLocaleString() || '-'}</td>
                <td>{new Date(dataset.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
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
    </div>
  );
}
