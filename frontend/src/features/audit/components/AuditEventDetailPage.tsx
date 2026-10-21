/**
 * Audit Event Detail Page
 * Shows detailed information about a single audit event
 */

import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { useAuditEvent } from '../hooks/useAudit';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './AuditEventDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function AuditEventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: event, isLoading, error, refetch } = useAuditEvent(id || null);

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error) {
    return (
      <ErrorDisplay error={error} title="Failed to load audit event" onRetry={() => refetch()} />
    );
  }

  if (!event) {
    return (
      <EmptyState
        title="Audit event not found"
        message="The requested audit event could not be found."
        action={{
          label: 'Back to Audit Events',
          onClick: () => navigate('/audit'),
        }}
      />
    );
  }

  return (
    <div className="audit-event-detail-page" data-testid="audit-event-detail-page">
      <div className="audit-detail-header">
        <Button
 variant="secondary"
 onClick={() => navigate('/audit')}
 aria-label="Back to audit events">
          ← Back to Audit Events
        </Button>
        <h1>Audit Event Details</h1>
      </div>

      <div className="audit-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Audit', href: '/audit' },
            { label: 'Event' },
          ]}
        />
        <div className="audit-detail-section">
          <h2>Basic Information</h2>
          <dl className="audit-detail-list">
            <dt>ID</dt>
            <dd>
              <UuidWithCopy value={event.id} label="Event ID" />
            </dd>
            <dt>Timestamp</dt>
            <dd>{new Date(event.timestamp).toLocaleString()}</dd>
            <dt>Tenant</dt>
            <dd>
              {event.tenant_name ??
                (typeof event.tenant === 'object' && event.tenant !== null && 'name' in event.tenant
                  ? (event.tenant as { name: string }).name
                  : typeof event.tenant === 'string'
                    ? event.tenant
                    : '—')}
            </dd>
            <dt>Actor</dt>
            <dd>
              {event.actor_user_email ??
                (typeof event.actor_user === 'object' && event.actor_user !== null && 'email' in event.actor_user
                  ? (event.actor_user as { email: string }).email
                  : typeof event.actor_user === 'string'
                    ? event.actor_user
                    : 'SYSTEM')}
            </dd>
          </dl>
        </div>

        <div className="audit-detail-section">
          <h2>Action Details</h2>
          <dl className="audit-detail-list">
            <dt>Resource Type</dt>
            <dd>{event.resource_type}</dd>
            <dt>Resource ID</dt>
            <dd>{event.resource_id || '—'}</dd>
            <dt>Action</dt>
            <dd>{event.action}</dd>
            <dt>Result</dt>
            <dd>
              <span className={`audit-result-badge ${event.result.toLowerCase()}`}>
                {event.result}
              </span>
            </dd>
          </dl>
        </div>

        {event.details_json && Object.keys(event.details_json).length > 0 && (
          <div className="audit-detail-section">
            <h2>Additional Details</h2>
            <pre className="audit-details-json">{JSON.stringify(event.details_json, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
