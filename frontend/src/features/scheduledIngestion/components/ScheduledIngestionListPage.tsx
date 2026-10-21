/**
 * Scheduled Ingestion List Page
 * Lists scheduled ingestions with status filter
 */

import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import type { ScheduledIngestionStatus } from '../../../shared/types/scheduledIngestion';
import { useScheduledIngestions } from '../hooks/useScheduledIngestion';
import './ScheduledIngestionListPage.css';
import { Button } from '../../../shared/components/Button';

const STATUS_OPTIONS: { value: '' | ScheduledIngestionStatus; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'PAUSED', label: 'Paused' },
  { value: 'ERROR', label: 'Error' },
];

export function ScheduledIngestionListPage() {
  const navigate = useNavigate();
  // W12.9 — real server-side pagination (the W5.4 AuditEventListPage
  // pattern): `page` is state that drives the API request, not a
  // hardcoded 1 with console.log button stubs.
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<'' | ScheduledIngestionStatus>('');

  const filters = {
    page,
    page_size: pageSize,
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useScheduledIngestions(filters);

  const handleRowClick = (id: string) => {
    navigate(`/scheduled-ingestions/${id}`);
  };

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  // Track B structural inversion: header + filter bar render unconditionally.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay
        error={error}
        title="Failed to load scheduled ingestions"
        onRetry={() => refetch()}
      />
    );
  } else if (results.length === 0) {
    mainContent = (
      <EmptyState
        title="No scheduled ingestions"
        message={
          statusFilter
            ? `No scheduled ingestions with status "${statusFilter}".`
            : 'No scheduled ingestions yet. Create one to automate data ingestion from external sources.'
        }
        action={{
          label: 'Create Schedule',
          onClick: () => navigate('/scheduled-ingestions/create'),
        }}
      />
    );
  } else {
    mainContent = (
      <>
        <table className="scheduled-ingestion-table" aria-label="Scheduled ingestions">
          <thead>
            <tr>
              <th>Name</th>
              <th>Source Type</th>
              <th>Schedule</th>
              <th>Status</th>
              <th>Next Run</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {results.map((schedule) => (
              <tr
                key={schedule.id}
                className="row-link"
                onClick={() => handleRowClick(schedule.id)}
                onKeyDown={(e) => e.key === 'Enter' && handleRowClick(schedule.id)}
                role="button"
                tabIndex={0}
              >
                <td>{schedule.name}</td>
                <td>{schedule.source_type}</td>
                <td>{schedule.schedule_type}</td>
                <td>
                  <span
                    className={`scheduled-ingestion-status-badge ${schedule.status.toLowerCase()}`}
                  >
                    {schedule.status}
                  </span>
                </td>
                <td>
                  {schedule.next_run_at
                    ? new Date(schedule.next_run_at).toLocaleString()
                    : '—'}
                </td>
                <td>{new Date(schedule.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="scheduled-ingestion-list-pagination">
          <span
            className="pagination-info"
            data-testid="scheduled-ingestion-pagination-info"
          >
            {count} result{count !== 1 ? 's' : ''} · Page {page}
          </span>
          <div className="scheduled-ingestion-list-pagination-buttons">
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={!data?.previous}
              data-testid="scheduled-ingestion-prev-page-btn"
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => p + 1)}
              disabled={!data?.next}
              data-testid="scheduled-ingestion-next-page-btn"
            >
              Next
            </Button>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="scheduled-ingestion-list-page" data-testid="scheduled-ingestion-list-page">
      <div className="scheduled-ingestion-list-header">
        <h1>Scheduled Ingestion</h1>
        <Button variant="primary" onClick={() => navigate('/scheduled-ingestions/create')}>
          Create Schedule
        </Button>
      </div>

      <div className="scheduled-ingestion-list-filters">
        <label htmlFor="scheduled-ingestion-status-filter">Status</label>
        <select
          id="scheduled-ingestion-status-filter"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter((e.target.value || '') as '' | ScheduledIngestionStatus);
            setPage(1); // W12.9: discrete filter change resets to page 1
          }}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {mainContent}
    </div>
  );
}
