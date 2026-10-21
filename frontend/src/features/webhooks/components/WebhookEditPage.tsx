/**
 * Webhook Edit Page
 * Form: name, URL, secret (required by API), event_types
 */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { WebhookUpdateRequest } from '../../../shared/types/webhooks';
import { useUpdateWebhook, useWebhook, useWebhookEventTypes } from '../hooks/useWebhooks';
import './WebhookCreatePage.css';
import { Button } from '../../../shared/components/Button';

export function WebhookEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: webhook, isLoading: loadingWebhook, error: webhookError } = useWebhook(id ?? null);
  const { data: eventTypesData, isLoading: loadingEvents } = useWebhookEventTypes(false);
  const updateMutation = useUpdateWebhook();

  const eventTypes = eventTypesData?.event_types ?? [];

  useEffect(() => {
    if (webhook) {
      setName(webhook.name);
      setUrl(webhook.url);
      setSelectedEvents(Array.isArray(webhook.event_types) ? [...webhook.event_types] : []);
    }
  }, [webhook]);

  const toggleEvent = (value: string) => {
    setSelectedEvents((prev) =>
      prev.includes(value) ? prev.filter((e) => e !== value) : [...prev, value]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSubmitError(null);
    if (!name.trim()) {
      setSubmitError('Name is required');
      return;
    }
    if (!url.trim()) {
      setSubmitError('URL is required');
      return;
    }
    if (!secret.trim()) {
      setSubmitError('Secret is required (re-enter to confirm)');
      return;
    }
    if (selectedEvents.length === 0) {
      setSubmitError('Select at least one event type');
      return;
    }
    try {
      const payload: WebhookUpdateRequest = {
        name: name.trim(),
        url: url.trim(),
        secret: secret,
        event_types: selectedEvents,
      };
      await updateMutation.mutateAsync({ id, data: payload });
      navigate(`/webhooks/${id}`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to update webhook');
    }
  };

  if (loadingWebhook || !webhook) {
    if (webhookError) {
      return (
        <ErrorDisplay
          error={webhookError}
          title="Failed to load webhook"
          onRetry={() => window.location.reload()}
        />
      );
    }
    return <LoadingSpinner message="Loading webhook..." />;
  }

  if (loadingEvents) {
    return <LoadingSpinner message="Loading event types..." />;
  }

  return (
    <div className="webhook-create-page">
      <Button variant="ghost" onClick={() => navigate(`/webhooks/${id}`)}>
        ← Back to Webhook
      </Button>
      <h1>Edit webhook</h1>

      <form className="webhook-create-form" onSubmit={handleSubmit}>
        {submitError && (
          <div className="webhook-form-error" role="alert">
            {submitError}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="webhook-edit-name">Name (required)</label>
          <input
            id="webhook-edit-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="webhook-edit-url">URL (required)</label>
          <input
            id="webhook-edit-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="webhook-edit-secret">Secret (required — re-enter to confirm)</label>
          <input
            id="webhook-edit-secret"
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            required
            placeholder="Re-enter secret"
            autoComplete="new-password"
          />
        </div>

        <div className="form-group">
          <label>Event types (select at least one)</label>
          <div className="webhook-event-types-list">
            {eventTypes.slice(0, 30).map((opt) => (
              <label key={opt.value} className="webhook-event-checkbox">
                <input
                  type="checkbox"
                  checked={selectedEvents.includes(opt.value)}
                  onChange={() => toggleEvent(opt.value)}
                />
                <span>{opt.label || opt.value}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="form-actions">
          <Button
 variant="secondary"
 onClick={() => navigate(`/webhooks/${id}`)}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={updateMutation.isPending}>
            Save
          </Button>
        </div>
      </form>
    </div>
  );
}
