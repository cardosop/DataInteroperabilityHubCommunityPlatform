/**
 * Webhook Detail Page
 * View webhook; actions: Edit, Delete (with confirmation), Test
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { useDeleteWebhook, useTestWebhook, useWebhook } from '../hooks/useWebhooks';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './WebhookDetailPage.css';
import { Button } from '../../../shared/components/Button';

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

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load webhook"
        onRetry={() => refetch()}
      />
    );
  }

  if (isLoading || !webhook) {
    return <DetailPageSkeleton />;
  }

  return (
    <div className="webhook-detail-page">
      <div className="webhook-detail-header">
        <Button variant="ghost" onClick={() => navigate('/webhooks')}>
          ← Back to Webhooks
        </Button>
        <div className="webhook-detail-actions">
          <Button
 variant="secondary"
 onClick={() => navigate(`/webhooks/${id}/edit`)}>
            Edit
          </Button>
          <Button
 variant="secondary"
 onClick={handleTest}
 loading={testMutation.isPending}>
            Test
          </Button>
          <Button variant="danger" onClick={() => setShowDeleteConfirm(true)}>
            Delete
          </Button>
        </div>
      </div>

      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Webhooks', href: '/webhooks' },
          { label: webhook.name || 'Webhook' },
        ]}
      />
      <h1>{webhook.name}</h1>
      {id && (
        <div className="webhook-uuid" data-testid="webhook-uuid">
          <UuidWithCopy value={id} label="Webhook ID" />
        </div>
      )}

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
              <Button
 variant="secondary"
 onClick={() => setShowDeleteConfirm(false)}>
                Cancel
              </Button>
              <Button
 variant="danger"
 onClick={handleDelete}
 loading={deleteMutation.isPending}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
