/**
 * Scheduled Ingestion List Page
 * Lists scheduled ingestions with status filter
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ScheduledIngestionStatus } from '../../../shared/types/scheduledIngestion';
import { useScheduledIngestions } from '../hooks/useScheduledIngestion';
import './ScheduledIngestionListPage.css';

const STATUS_OPTIONS: { value: '' | ScheduledIngestionStatus; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'PAUSED', label: 'Paused' },
  { value: 'ERROR', label: 'Error' },
];

export function ScheduledIngestionListPage() {
  const navigate = useNavigate();
  const [page] = useState(1);
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

  if (isLoading) {
    return <LoadingSpinner message="Loading scheduled ingestions..." />;
  }

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load scheduled ingestions"
        onRetry={() => refetch()}
      />
    );
  }

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  return (
    <div className="scheduled-ingestion-list-page" data-testid="scheduled-ingestion-list-page">
      <div className="scheduled-ingestion-list-header">
        <h1>Scheduled Ingestion</h1>
        <button
          type="button"
          className="btn-primary"
          onClick={() => navigate('/scheduled-ingestions/create')}
        >
          Create Schedule
        </button>
      </div>

      <div className="scheduled-ingestion-list-filters">
        <label htmlFor="scheduled-ingestion-status-filter">Status</label>
        <select
          id="scheduled-ingestion-status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter((e.target.value || '') as '' | ScheduledIngestionStatus)}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {results.length === 0 ? (
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
      ) : (
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
                    <span className={`scheduled-ingestion-status-badge ${schedule.status.toLowerCase()}`}>
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
