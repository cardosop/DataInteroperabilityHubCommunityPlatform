/**
 * Scheduled Export List Page
 * Lists scheduled exports with status filter
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ScheduledExportStatus } from '../../../shared/types/scheduledExport';
import { useScheduledExports } from '../hooks/useScheduledExport';
import './ScheduledExportListPage.css';

const STATUS_OPTIONS: { value: '' | ScheduledExportStatus; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'PAUSED', label: 'Paused' },
  { value: 'ERROR', label: 'Error' },
];

export function ScheduledExportListPage() {
  const navigate = useNavigate();
  const [page] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<'' | ScheduledExportStatus>('');

  const filters = {
    page,
    page_size: pageSize,
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useScheduledExports(filters);

  const handleRowClick = (id: string) => {
    navigate(`/scheduled-exports/${id}`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading scheduled exports..." />;
  }

  const results = data?.results ?? [];
  const count = data?.count ?? 0;

  return (
    <div className="scheduled-export-list-page" data-testid="scheduled-export-list-page">
      <div className="scheduled-export-list-header">
        <h1>Scheduled Export</h1>
        <button
          type="button"
          className="btn-primary"
          onClick={() => navigate('/scheduled-exports/create')}
        >
          Create Export
        </button>
      </div>

      {error && (
        <div style={{ marginBottom: 'var(--spacing-lg)' }}>
          <ErrorDisplay
            error={error}
            title="Failed to load scheduled exports"
            onRetry={() => refetch()}
          />
        </div>
      )}

      <div className="scheduled-export-list-filters">
        <label htmlFor="scheduled-export-status-filter">Status</label>
        <select
          id="scheduled-export-status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter((e.target.value || '') as '' | ScheduledExportStatus)}
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
          title="No scheduled exports"
          message={
            statusFilter
              ? `No scheduled exports with status "${statusFilter}".`
              : 'No scheduled exports yet. Create one to automate data exports to external destinations.'
          }
          action={{
            label: 'Create Export',
            onClick: () => navigate('/scheduled-exports/create'),
          }}
        />
      ) : (
        <>
          <table className="scheduled-export-table" aria-label="Scheduled exports">
            <thead>
              <tr>
                <th>Name</th>
                <th>Destination Type</th>
                <th>Schedule</th>
                <th>Status</th>
                <th>Next Run</th>
                <th>Last Run</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {results.map((export_) => (
                <tr
                  key={export_.id}
                  className="row-link"
                  data-testid="scheduled-export-row"
                  onClick={() => handleRowClick(export_.id)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRowClick(export_.id)}
                  role="button"
                  tabIndex={0}
                >
                  <td>{export_.name}</td>
                  <td>{export_.destination_type}</td>
                  <td>{export_.schedule_config.cron}</td>
                  <td>
                    <span
                      className={`scheduled-export-status-badge ${export_.status.toLowerCase()}`}
                    >
                      {export_.status}
                    </span>
                  </td>
                  <td>
                    {export_.next_run_at ? new Date(export_.next_run_at).toLocaleString() : '—'}
                  </td>
                  <td>
                    {export_.last_run_at ? new Date(export_.last_run_at).toLocaleString() : '—'}
                  </td>
                  <td>{new Date(export_.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="scheduled-export-list-pagination">
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
