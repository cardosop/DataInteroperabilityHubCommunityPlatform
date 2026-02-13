/**
 * Webhook List Page
 * Lists webhooks with link to create and detail (real API)
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useWebhooks } from '../hooks/useWebhooks';
import './WebhookListPage.css';

export function WebhookListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const { data, isLoading, error, refetch } = useWebhooks({ page, page_size: pageSize });

  if (isLoading) return <LoadingSpinner message="Loading webhooks..." />;
  if (error) {
    return <ErrorDisplay error={error} title="Failed to load webhooks" onRetry={() => refetch()} />;
  }

  const results = data?.results ?? [];
  const totalPages = data?.total_pages ?? 0;

  if (!data || results.length === 0) {
    return (
      <div className="webhook-list-page">
        <div className="webhook-list-header">
          <h1>Webhooks</h1>
          <button
            type="button"
            className="btn-primary"
            onClick={() => navigate('/webhooks/create')}
          >
            Create webhook
          </button>
        </div>
        <EmptyState
          title="No webhooks"
          message="Create a webhook to receive event notifications at a URL."
          action={{ label: 'Create webhook', onClick: () => navigate('/webhooks/create') }}
        />
      </div>
    );
  }

  return (
    <div className="webhook-list-page">
      <div className="webhook-list-header">
        <h1>Webhooks</h1>
        <button type="button" className="btn-primary" onClick={() => navigate('/webhooks/create')}>
          Create webhook
        </button>
      </div>

      <div className="webhook-list-table-wrapper">
        <table className="webhook-list-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Events</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {results.map((w) => (
              <tr
                key={w.id}
                className="webhook-list-row"
                onClick={() => navigate(`/webhooks/${w.id}`)}
                onKeyDown={(e) => e.key === 'Enter' && navigate(`/webhooks/${w.id}`)}
                role="button"
                tabIndex={0}
              >
                <td>
                  <strong>{w.name}</strong>
                </td>
                <td className="webhook-list-url">{w.url}</td>
                <td>{Array.isArray(w.event_types) ? w.event_types.length : 0} events</td>
                <td>
                  <span
                    className={`webhook-status-badge webhook-status-${(w.status ?? '').toLowerCase()}`}
                  >
                    {w.status}
                  </span>
                </td>
                <td>{new Date(w.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="webhook-list-pagination">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={!data.has_previous}
          >
            Previous
          </button>
          <span>
            Page {data.page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={!data.has_next}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
