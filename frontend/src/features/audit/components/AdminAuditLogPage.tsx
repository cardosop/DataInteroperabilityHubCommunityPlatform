/**
 * Phase 260.4.H — Admin audit log search.
 *
 * TENANT_ADMIN-only page at ``/admin/audit-log/`` for searching the
 * audit log by resource. The route accepts ``?resource_type=...`` +
 * ``?resource_id=...`` query params so deep links from detail pages
 * (e.g. "View audit history" on a file) land directly on the
 * filtered view without the user having to re-type the UUID.
 *
 * Differences from the existing ``AuditEventListPage`` at ``/audit/``:
 *   - This page exposes a ``resource_id`` filter input + URL param.
 *   - This page is TENANT_ADMIN-gated at the route level (the
 *     existing list is AUDITOR + PLATFORM_ADMIN-gated; both share
 *     the backend's ``AUDIT_READ_ROLES`` set including TENANT_ADMIN
 *     so the wire contract stays one role list).
 *   - This page emphasises the CSV export workflow for compliance
 *     evidence: "Export audit log for resource X" is the primary
 *     CTA on the right side of the header.
 *
 * Data plane is the same audit infrastructure (``useAuditEvents``,
 * ``auditService.export``) — no new wire contracts. The whole page
 * is composition of existing primitives plus a resource_id filter
 * input AND deep-link behaviour from URL query params.
 */

import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { Button } from '../../../shared/components/Button';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { useToast } from '../../../shared/components/Toast';
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

/**
 * Sync a stateful filter to the URL ``?key=value`` so refreshing
 * the page (or copy-pasting the URL into another tenant-admin
 * seat) preserves the search context. ``replaceState`` (NOT push)
 * so filter typing doesn't pollute the browser back-stack.
 */
function useFilterUrlSync(
  searchParams: URLSearchParams,
  setSearchParams: (next: URLSearchParams, opts?: { replace?: boolean }) => void,
  key: string,
  value: string,
) {
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      if (next.get(key) === value) return;
      next.set(key, value);
    } else {
      if (!next.has(key)) return;
      next.delete(key);
    }
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, value]);
}

export function AdminAuditLogPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Initial values come from the URL so deep-links land on the
  // pre-filtered view. The "?resource_type=FILE&resource_id=..."
  // pattern from the spec is the primary entry point.
  const [resourceTypeFilter, setResourceTypeFilter] = useState(
    () => searchParams.get('resource_type') ?? '',
  );
  const [resourceIdFilter, setResourceIdFilter] = useState(
    () => searchParams.get('resource_id') ?? '',
  );
  const [actionFilter, setActionFilter] = useState('');
  const [actorUserIdFilter, setActorUserIdFilter] = useState('');
  const [startDateFilter, setStartDateFilter] = useState('');
  const [endDateFilter, setEndDateFilter] = useState('');
  const [isExporting, setIsExporting] = useState(false);
  // R1 audit GAP-C — pagination. Default page-size 50 matches the
  // existing dataset / asset list pages so a TENANT_ADMIN doing
  // compliance work isn't artificially capped at one screen.
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  // Push the resource_type / resource_id filters back to the URL on
  // every change so the URL is always shareable.
  useFilterUrlSync(searchParams, setSearchParams, 'resource_type', resourceTypeFilter);
  useFilterUrlSync(searchParams, setSearchParams, 'resource_id', resourceIdFilter);

  const debouncedActorUserId = useDebouncedValue(actorUserIdFilter, 300);
  // Debounce the resource_id input too — UUIDs are typed character-
  // by-character, no point firing 36 requests for one paste.
  const debouncedResourceId = useDebouncedValue(resourceIdFilter, 300);

  const formatDateForAPI = (dateStr: string): string | undefined => {
    if (!dateStr) return undefined;
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
    page_size: PAGE_SIZE,
    resource_type: resourceTypeFilter || undefined,
    resource_id: debouncedResourceId || undefined,
    action: actionFilter || undefined,
    actor_user_id: debouncedActorUserId || undefined,
    start_date: formatDateForAPI(startDateFilter),
    end_date: formatDateForAPI(endDateFilter),
  };

  // R1 audit GAP-C — when any filter changes, reset to page 1 so
  // the user doesn't land on an empty page-3 of an unrelated query.
  // Only the discrete filter values feed this reset; the debounced
  // text inputs already have their own settling step.
  useEffect(() => {
    setPage(1);
  }, [
    resourceTypeFilter,
    debouncedResourceId,
    actionFilter,
    debouncedActorUserId,
    startDateFilter,
    endDateFilter,
  ]);

  const { data, isLoading, error, refetch } = useAuditEvents(filters);

  const handleExportCsv = async () => {
    setIsExporting(true);
    try {
      const exportFilters = {
        resource_type: resourceTypeFilter || undefined,
        resource_id: debouncedResourceId || undefined,
        action: actionFilter || undefined,
        actor_user_id: debouncedActorUserId || undefined,
        start_date: formatDateForAPI(startDateFilter),
        end_date: formatDateForAPI(endDateFilter),
      };
      const blob = await auditService.export('csv', exportFilters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // Filename embeds resource_id when filtered for compliance
      // traceability — auditor can save the file with the
      // resource UUID in the name.
      a.download = debouncedResourceId
        ? `audit_log_${debouncedResourceId}.csv`
        : 'audit_log.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Audit log exported to CSV.');
    } catch {
      toast.error('Failed to export audit log. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay
        error={error}
        title="Failed to load audit log"
        onRetry={() => refetch()}
      />
    );
  } else if (results.length === 0) {
    mainContent = (
      <EmptyState
        title="No audit events"
        message={
          debouncedResourceId
            ? `No events match resource_id ${debouncedResourceId} with the current filters.`
            : 'Use the filters above to narrow the audit log to a specific resource.'
        }
        data-testid="admin-audit-log-empty-state"
      />
    );
  } else {
    mainContent = (
      <>
        <table className="audit-event-table" aria-label="Audit log">
          <thead>
            <tr>
              <th scope="col">Timestamp</th>
              <th scope="col">Resource Type</th>
              <th scope="col">Resource ID</th>
              <th scope="col">Action</th>
              <th scope="col">Actor</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {results.map((event) => (
              <tr
                key={event.id}
                className="row-link"
                onClick={() => navigate(`/audit/${event.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/audit/${event.id}`);
                  }
                }}
                role="row"
                tabIndex={0}
                aria-label={`Audit event ${event.action} on ${event.resource_type}`}
              >
                <td>{new Date(event.timestamp).toLocaleString()}</td>
                <td>{event.resource_type}</td>
                <td className="audit-resource-id-cell">
                  <code>{event.resource_id ?? '—'}</code>
                </td>
                <td>{event.action}</td>
                <td>{event.actor_user_email ?? 'SYSTEM'}</td>
                <td>
                  <span className={`audit-result-badge ${event.result.toLowerCase()}`}>
                    {event.result}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="audit-list-pagination">
          <span className="pagination-info" data-testid="admin-audit-log-pagination-info">
            {count} result{count !== 1 ? 's' : ''} · Page {page}
          </span>
          <div className="audit-list-pagination-buttons">
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={!data?.previous}
              data-testid="admin-audit-log-prev-page-btn"
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => p + 1)}
              disabled={!data?.next}
              data-testid="admin-audit-log-next-page-btn"
            >
              Next
            </Button>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="audit-event-list-page" data-testid="admin-audit-log-page">
      <div className="audit-list-header">
        <h1>Audit Log Search</h1>
        <div className="audit-export-buttons">
          <Button
            variant="primary"
            onClick={() => void handleExportCsv()}
            disabled={isExporting || count === 0}
            data-testid="admin-audit-log-export-csv-btn"
            aria-label="Export audit log to CSV for compliance"
          >
            {isExporting ? 'Exporting…' : 'Export CSV'}
          </Button>
        </div>
      </div>

      <div className="audit-list-filters">
        <div className="filter-group">
          <label htmlFor="admin-audit-resource-type">Resource Type</label>
          <select
            id="admin-audit-resource-type"
            data-testid="admin-audit-resource-type-filter"
            value={resourceTypeFilter}
            onChange={(e) => setResourceTypeFilter(e.target.value)}
          >
            {RESOURCE_TYPES.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="admin-audit-resource-id">Resource ID</label>
          <input
            id="admin-audit-resource-id"
            data-testid="admin-audit-resource-id-filter"
            type="text"
            value={resourceIdFilter}
            onChange={(e) => setResourceIdFilter(e.target.value)}
            placeholder="Resource UUID (e.g. file id)"
            spellCheck={false}
            autoComplete="off"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="admin-audit-action">Action</label>
          <input
            id="admin-audit-action"
            data-testid="admin-audit-action-filter"
            type="text"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="e.g. CREATED, FILE_RENAMED"
            spellCheck={false}
            autoComplete="off"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="admin-audit-actor">Actor User ID</label>
          <input
            id="admin-audit-actor"
            data-testid="admin-audit-actor-filter"
            type="text"
            value={actorUserIdFilter}
            onChange={(e) => setActorUserIdFilter(e.target.value)}
            placeholder="UUID"
            spellCheck={false}
            autoComplete="off"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="admin-audit-start-date">Start Date</label>
          <input
            id="admin-audit-start-date"
            data-testid="admin-audit-start-date-filter"
            type="datetime-local"
            value={startDateFilter}
            onChange={(e) => setStartDateFilter(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label htmlFor="admin-audit-end-date">End Date</label>
          <input
            id="admin-audit-end-date"
            data-testid="admin-audit-end-date-filter"
            type="datetime-local"
            value={endDateFilter}
            onChange={(e) => setEndDateFilter(e.target.value)}
          />
        </div>
      </div>

      {mainContent}
    </div>
  );
}
