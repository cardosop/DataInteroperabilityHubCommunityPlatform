/**
 * Webhook Detail Page
 * View webhook; actions: Edit, Delete (with confirmation), Test
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useDeleteWebhook, useTestWebhook, useWebhook } from '../hooks/useWebhooks';
import './WebhookDetailPage.css';

export function WebhookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: webhook, isLoading, error, refetch } = useWebhook(id ?? null);
  const deleteMutation = useDeleteWebhook();
  const testMutation = useTestWebhook();

  const handleDelete = async () => {
    if (!id) return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/webhooks');
    } catch {
      // Error handled by mutation
    }
  };

  const handleTest = async () => {
    if (!id) return;
    try {
      await testMutation.mutateAsync(id);
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading webhook..." />;
  if (error || !webhook) {
    return (
      <ErrorDisplay
        error={error ?? new Error('Webhook not found')}
        title="Failed to load webhook"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="webhook-detail-page">
      <div className="webhook-detail-header">
        <button type="button" className="btn-back" onClick={() => navigate('/webhooks')}>
          ← Back to Webhooks
        </button>
        <div className="webhook-detail-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate(`/webhooks/${id}/edit`)}
          >
            Edit
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleTest}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? 'Sending...' : 'Test'}
          </button>
          <button type="button" className="btn-danger" onClick={() => setShowDeleteConfirm(true)}>
            Delete
          </button>
        </div>
      </div>

      <h1>{webhook.name}</h1>

      <dl className="webhook-detail-dl">
        <dt>URL</dt>
        <dd className="webhook-detail-url">{webhook.url}</dd>
        <dt>Status</dt>
        <dd>
          <span
            className={`webhook-status-badge webhook-status-${(webhook.status ?? '').toLowerCase()}`}
          >
            {webhook.status}
          </span>
        </dd>
        <dt>Event types</dt>
        <dd>
          <ul className="webhook-detail-events">
            {Array.isArray(webhook.event_types)
              ? webhook.event_types.map((e) => <li key={e}>{e}</li>)
              : '—'}
          </ul>
        </dd>
        <dt>Max retries</dt>
        <dd>{webhook.max_retries ?? '—'}</dd>
        <dt>Created</dt>
        <dd>{new Date(webhook.created_at).toLocaleString()}</dd>
        <dt>Updated</dt>
        <dd>{new Date(webhook.updated_at).toLocaleString()}</dd>
      </dl>

      {showDeleteConfirm && (
        <div
          className="webhook-delete-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="webhook-delete-title"
        >
          <div className="webhook-delete-dialog">
            <h3 id="webhook-delete-title">Delete webhook?</h3>
            <p>
              Are you sure you want to delete <strong>{webhook.name}</strong>? This cannot be
              undone.
            </p>
            <div className="webhook-delete-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
