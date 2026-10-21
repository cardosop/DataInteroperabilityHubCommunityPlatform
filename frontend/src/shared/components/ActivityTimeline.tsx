/**
 * ActivityTimeline — Phase 224.3.3
 *
 * Vertical timeline of sanitized audit events for a single resource. Drives
 * the "Activity" tab on Asset/Contract/Order/AccessRequest detail pages.
 *
 * Data comes from ``useResourceActivity`` (backed by ``/api/v1/audit/
 * audit-events/resource-activity/``) which returns server-side-scrubbed
 * entries — we assume ``details`` is safe to render without further
 * sanitisation here.
 */

import { useResourceActivity } from '../../features/audit/hooks/useAudit';
import type { ResourceActivityEvent, ResourceType } from '../types/audit';
import { ErrorDisplay } from './ErrorDisplay';
import { LoadingSpinner } from './LoadingSpinner';
import './ActivityTimeline.css';

export interface ActivityTimelineProps {
  resourceType: ResourceType;
  resourceId: string;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function ActivityAvatar({ name, eventId }: { name: string; eventId: string }) {
  const isSystem = name === 'System';
  return (
    <span
      className={`activity-avatar ${isSystem ? 'activity-avatar--system' : ''}`}
      data-testid={`activity-avatar-${eventId}`}
      data-system={isSystem ? 'true' : 'false'}
      aria-hidden="true"
    >
      {isSystem ? '⚙' : initials(name)}
    </span>
  );
}

function ActivityDetails({
  details,
  eventId,
}: {
  details: Record<string, unknown>;
  eventId: string;
}) {
  const entries = Object.entries(details ?? {});
  if (entries.length === 0) return null;
  return (
    <dl className="activity-details" data-testid={`activity-details-${eventId}`}>
      {entries.map(([key, value]) => (
        <div key={key} className="activity-details__row">
          <dt>{key}</dt>
          <dd>{renderValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function renderValue(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function ActivityItem({ event }: { event: ResourceActivityEvent }) {
  const resultClass = `activity-item--${event.result.toLowerCase()}`;
  return (
    <li
      className={`activity-item ${resultClass}`}
      data-testid={`activity-item-${event.id}`}
    >
      <ActivityAvatar name={event.actor_display_name} eventId={event.id} />
      <div className="activity-item__body">
        <div className="activity-item__header">
          <span className="activity-item__action">{event.action}</span>
          <span className="activity-item__actor">{event.actor_display_name}</span>
          <time dateTime={event.timestamp} className="activity-item__time">
            {formatTimestamp(event.timestamp)}
          </time>
        </div>
        <ActivityDetails details={event.details} eventId={event.id} />
      </div>
    </li>
  );
}

export function ActivityTimeline({ resourceType, resourceId }: ActivityTimelineProps) {
  const { data, isLoading, error } = useResourceActivity(resourceType, resourceId);

  if (isLoading) {
    return (
      <div className="activity-timeline" data-testid="activity-timeline-loading">
        <LoadingSpinner message="Loading activity..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="activity-timeline" data-testid="activity-timeline-error">
        <ErrorDisplay error={error} title="Failed to load activity" />
      </div>
    );
  }

  const events = data?.results ?? [];
  if (events.length === 0) {
    return (
      <div className="activity-timeline" data-testid="activity-timeline-empty">
        <p className="activity-timeline__empty">No activity recorded for this resource yet.</p>
      </div>
    );
  }

  return (
    <div className="activity-timeline" data-testid="activity-timeline">
      <ol className="activity-timeline__list">
        {events.map((e) => (
          <ActivityItem key={e.id} event={e} />
        ))}
      </ol>
    </div>
  );
}
