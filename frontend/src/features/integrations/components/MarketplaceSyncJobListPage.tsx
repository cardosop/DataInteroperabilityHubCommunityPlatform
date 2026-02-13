/**
 * Marketplace Sync Job List Page
 * View and manage marketplace sync jobs
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMarketplaceSyncJobs } from '../hooks/useMarketplaceSyncJobs';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { SyncJobStatus, SyncDirection } from '../../../shared/types/integrations';
import './MarketplaceSyncJobListPage.css';

export function MarketplaceSyncJobListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<SyncJobStatus | ''>('');
  const [directionFilter, setDirectionFilter] = useState<SyncDirection | ''>('');

  const filters = {
    page,
    page_size: pageSize,
    status: statusFilter || undefined,
    direction: directionFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useMarketplaceSyncJobs(filters);

  const handleSyncJobClick = (jobId: string) => {
    navigate(`/integrations/sync-jobs/${jobId}`);
  };

  const handleCreateSyncJob = () => {
    navigate('/integrations/sync-jobs/create');
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading sync jobs..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load sync jobs" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No sync jobs found"
        message={statusFilter || directionFilter
          ? "Try adjusting your filters to see more results."
          : "No sync jobs have been created yet."}
        action={!statusFilter && !directionFilter
          ? { label: 'Create Sync Job', onClick: handleCreateSyncJob }
          : undefined}
      />
    );
  }

  return (
    <div className="sync-job-list-page">
      <div className="sync-job-list-header">
        <h1>Marketplace Sync Jobs</h1>
        <button className="btn-primary" onClick={handleCreateSyncJob} type="button">
          Create Sync Job
        </button>
      </div>

      <div className="sync-job-list-filters">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as SyncJobStatus | '');
            setPage(1);
          }}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={SyncJobStatus.PENDING}>Pending</option>
          <option value={SyncJobStatus.RUNNING}>Running</option>
          <option value={SyncJobStatus.COMPLETED}>Completed</option>
          <option value={SyncJobStatus.FAILED}>Failed</option>
          <option value={SyncJobStatus.PARTIAL}>Partial</option>
          <option value={SyncJobStatus.CANCELLED}>Cancelled</option>
        </select>
        <select
          value={directionFilter}
          onChange={(e) => {
            setDirectionFilter(e.target.value as SyncDirection | '');
            setPage(1);
          }}
          className="filter-select"
        >
          <option value="">All Directions</option>
          <option value={SyncDirection.PUSH}>Push</option>
          <option value={SyncDirection.PULL}>Pull</option>
          <option value={SyncDirection.BIDIRECTIONAL}>Bidirectional</option>
        </select>
      </div>

      <div className="sync-job-list-table">
        <table>
          <thead>
            <tr>
              <th>Connection</th>
              <th>Direction</th>
              <th>Status</th>
              <th>Items Synced</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((job) => (
              <tr
                key={job.id}
                onClick={() => handleSyncJobClick(job.id)}
                className="sync-job-row"
              >
                <td>{job.connection.name}</td>
                <td>{job.direction}</td>
                <td>
                  <span className={`sync-job-status sync-job-status-${job.status.toLowerCase()}`}>
                    {job.status}
                  </span>
                </td>
                <td>
                  {job.items_synced !== undefined ? job.items_synced : '-'}
                  {job.items_failed !== undefined && job.items_failed > 0 && (
                    <span className="sync-job-failed"> ({job.items_failed} failed)</span>
                  )}
                </td>
                <td>{new Date(job.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    className="btn-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSyncJobClick(job.id);
                    }}
                    type="button"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.count > pageSize && (
        <div className="sync-job-list-pagination">
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            type="button"
          >
            Previous
          </button>
          <span className="pagination-info">
            Page {page} of {Math.ceil(data.count / pageSize)}
          </span>
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(data.count / pageSize)}
            type="button"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
