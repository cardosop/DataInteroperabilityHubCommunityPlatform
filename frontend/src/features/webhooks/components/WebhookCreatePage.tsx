/**
 * Webhook Create Page
 * Form: name, URL, secret, events (from API); real API create
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { WebhookCreateRequest } from '../../../shared/types/webhooks';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useCreateWebhook, useWebhookEventTypes } from '../hooks/useWebhooks';
import './WebhookCreatePage.css';

export function WebhookCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    data: eventTypesData,
    isLoading: loadingEvents,
    error: eventTypesError,
  } = useWebhookEventTypes(false);
  const createMutation = useCreateWebhook();

  const eventTypes = eventTypesData?.event_types ?? [];

  const toggleEvent = (value: string) => {
    setSelectedEvents((prev) =>
      prev.includes(value) ? prev.filter((e) => e !== value) : [...prev, value]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      setSubmitError('Secret is required');
      return;
    }
    if (selectedEvents.length === 0) {
      setSubmitError('Select at least one event type');
      return;
    }
    try {
      const payload: WebhookCreateRequest = {
        name: name.trim(),
        url: url.trim(),
        secret: secret,
        event_types: selectedEvents,
      };
      const created = await createMutation.mutateAsync(payload);
      navigate(`/webhooks/${created.id}`);
    } catch (err) {
      const normalized = normalizeError(err);
      setSubmitError(normalized.error.message);
    }
  };

  if (loadingEvents) {
    return <LoadingSpinner message="Loading event types..." />;
  }

  if (eventTypesError) {
    return (
      <ErrorDisplay
        error={eventTypesError}
        title="Failed to load event types"
        onRetry={() => window.location.reload()}
      />
    );
  }

  return (
    <div className="webhook-create-page">
      <button type="button" className="btn-back" onClick={() => navigate('/webhooks')}>
        ← Back to Webhooks
      </button>
      <h1>Create webhook</h1>

      <form className="webhook-create-form" onSubmit={handleSubmit}>
        {submitError && (
          <div className="webhook-form-error" role="alert">
            {submitError}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="webhook-name">Name (required)</label>
          <input
            id="webhook-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="My webhook"
          />
        </div>

        <div className="form-group">
          <label htmlFor="webhook-url">URL (required)</label>
          <input
            id="webhook-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            placeholder="https://example.com/webhook"
          />
        </div>

        <div className="form-group">
          <label htmlFor="webhook-secret">Secret (required)</label>
          <input
            id="webhook-secret"
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            required
            placeholder="HMAC secret"
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
            {eventTypes.length > 30 && (
              <p className="webhook-event-hint">+ {eventTypes.length - 30} more (select above)</p>
            )}
          </div>
        </div>

        <div className="form-actions">
          <button type="button" className="btn-secondary" onClick={() => navigate('/webhooks')}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Creating...' : 'Create webhook'}
          </button>
        </div>
      </form>
    </div>
  );
}
