/**
 * Audit Event List Page
 * Lists audit events with filters (resource_type, action, actor, date range);
 * Export button (CSV/JSON)
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { AuditEventExportFormat } from '../../../shared/types/audit';
import { useAuditEvents } from '../hooks/useAudit';
import { auditService } from '../services/auditService';
import './AuditEventListPage.css';

const RESOURCE_TYPES = [
  { value: '', label: 'All' },
  { value: 'ASSET', label: 'Asset' },
  { value: 'CONTRACT', label: 'Contract' },
  { value: 'USER', label: 'User' },
  { value: 'TENANT', label: 'Tenant' },
  { value: 'AUTH', label: 'Auth' },
  { value: 'DATASET', label: 'Dataset' },
  { value: 'FILE', label: 'File' },
];

const ACTIONS = [
  { value: '', label: 'All' },
  { value: 'CREATED', label: 'Created' },
  { value: 'UPDATED', label: 'Updated' },
  { value: 'DELETED', label: 'Deleted' },
  { value: 'LOGIN', label: 'Login' },
  { value: 'LOGOUT', label: 'Logout' },
  { value: 'VIEWED', label: 'Viewed' },
  { value: 'DOWNLOADED', label: 'Downloaded' },
];

export function AuditEventListPage() {
  const navigate = useNavigate();
  const [page] = useState(1);
  const [pageSize] = useState(20);
  const [resourceTypeFilter, setResourceTypeFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [actorUserIdFilter, setActorUserIdFilter] = useState('');
  const [startDateFilter, setStartDateFilter] = useState('');
  const [endDateFilter, setEndDateFilter] = useState('');
  const [isExporting, setIsExporting] = useState(false);

  // Convert datetime-local to ISO format for API
  const formatDateForAPI = (dateStr: string): string | undefined => {
    if (!dateStr) return undefined;
    // datetime-local format is YYYY-MM-DDTHH:mm, convert to ISO 8601 with UTC timezone
    // Backend expects ISO 8601 format (e.g., "2025-01-29T10:30:00Z")
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return undefined;
      return date.toISOString();
    } catch {
      return undefined;
    }
  };

  const filters = {
    page,
    page_size: pageSize,
    resource_type: resourceTypeFilter || undefined,
    action: actionFilter || undefined,
    actor_user_id: actorUserIdFilter || undefined,
    start_date: formatDateForAPI(startDateFilter),
    end_date: formatDateForAPI(endDateFilter),
  };

  const { data, isLoading, error, refetch } = useAuditEvents(filters);

  const handleRowClick = (id: string) => {
    navigate(`/audit/${id}`);
  };

  const handleExport = async (format: AuditEventExportFormat) => {
    setIsExporting(true);
    try {
      const exportFilters = {
        resource_type: resourceTypeFilter || undefined,
        action: actionFilter || undefined,
        actor_user_id: actorUserIdFilter || undefined,
        start_date: formatDateForAPI(startDateFilter),
        end_date: formatDateForAPI(endDateFilter),
      };
      const blob = await auditService.export(format, exportFilters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_events.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Failed to export audit events. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading audit events..." />;
  }

  if (error) {
    return (
      <ErrorDisplay error={error} title="Failed to load audit events" onRetry={() => refetch()} />
    );
  }

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  return (
    <div className="audit-event-list-page" data-testid="audit-event-list-page">
      <div className="audit-list-header">
        <h1>Audit Events</h1>
        <div className="audit-export-buttons">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => handleExport('csv')}
            disabled={isExporting || count === 0}
            aria-label="Export CSV"
          >
            {isExporting ? 'Exporting...' : 'Export CSV'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => handleExport('json')}
            disabled={isExporting || count === 0}
            aria-label="Export JSON"
          >
            {isExporting ? 'Exporting...' : 'Export JSON'}
          </button>
        </div>
      </div>

      <div className="audit-list-filters">
        <div className="filter-group">
          <label htmlFor="audit-resource-type-filter">Resource Type</label>
          <select
            id="audit-resource-type-filter"
            value={resourceTypeFilter}
            onChange={(e) => setResourceTypeFilter(e.target.value)}
            aria-label="Filter by resource type"
          >
            {RESOURCE_TYPES.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="audit-action-filter">Action</label>
          <select
            id="audit-action-filter"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            aria-label="Filter by action"
          >
            {ACTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="audit-actor-filter">Actor User ID</label>
          <input
            id="audit-actor-filter"
            type="text"
            value={actorUserIdFilter}
            onChange={(e) => setActorUserIdFilter(e.target.value)}
            placeholder="UUID"
            aria-label="Filter by actor user ID"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="audit-start-date-filter">Start Date</label>
          <input
            id="audit-start-date-filter"
            type="datetime-local"
            value={startDateFilter}
            onChange={(e) => setStartDateFilter(e.target.value)}
            aria-label="Filter by start date"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="audit-end-date-filter">End Date</label>
          <input
            id="audit-end-date-filter"
            type="datetime-local"
            value={endDateFilter}
            onChange={(e) => setEndDateFilter(e.target.value)}
            aria-label="Filter by end date"
          />
        </div>
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="No audit events"
          message={
            resourceTypeFilter ||
            actionFilter ||
            actorUserIdFilter ||
            startDateFilter ||
            endDateFilter
              ? 'No audit events match the selected filters.'
              : 'No audit events found.'
          }
        />
      ) : (
        <>
          <table className="audit-event-table" aria-label="Audit events">
            <thead>
              <tr>
                <th scope="col">Timestamp</th>
                <th scope="col">Resource Type</th>
                <th scope="col">Action</th>
                <th scope="col">Actor</th>
                <th scope="col">Result</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {results.map((event) => (
                <tr
                  key={event.id}
                  className="row-link"
                  onClick={() => handleRowClick(event.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleRowClick(event.id);
                    }
                  }}
                  role="row"
                  tabIndex={0}
                  aria-label={`Audit event ${event.action} on ${event.resource_type}`}
                >
                  <td>{new Date(event.timestamp).toLocaleString()}</td>
                  <td>{event.resource_type}</td>
                  <td>{event.action}</td>
                  <td>
                    {event.actor_user_email ??
                      (typeof event.actor_user === 'object' &&
                      event.actor_user !== null &&
                      'email' in event.actor_user
                        ? (event.actor_user as { email: string }).email
                        : typeof event.actor_user === 'string'
                          ? event.actor_user
                          : 'SYSTEM')}
                  </td>
                  <td>
                    <span
                      className={`audit-result-badge ${event.result.toLowerCase()}`}
                      aria-label={`Result: ${event.result}`}
                    >
                      {event.result}
                    </span>
                  </td>
                  <td>
                    {Object.keys(event.details_json || {}).length > 0 ? (
                      <span
                        className="audit-details-indicator"
                        title={JSON.stringify(event.details_json)}
                      >
                        {Object.keys(event.details_json).length} field(s)
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="audit-list-pagination">
            <span className="pagination-info">
              {count} result{count !== 1 ? 's' : ''}
            </span>
            {data?.next && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  // TODO: Implement pagination
                  console.log('Next page');
                }}
              >
                Next
              </button>
            )}
            {data?.previous && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  // TODO: Implement pagination
                  console.log('Previous page');
                }}
              >
                Previous
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
