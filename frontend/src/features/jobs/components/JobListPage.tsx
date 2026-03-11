/**
 * Job List Page
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useJobs } from '../hooks/useJobs';
import './JobListPage.css';

export function JobListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useJobs({
    page,
    page_size: 50,
    ordering: '-created_at',
  });

  if (isLoading) return <LoadingSpinner message="Loading jobs..." />;
  if (error)
    return <ErrorDisplay error={error} title="Failed to load jobs" onRetry={() => refetch()} />;
  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No jobs found"
        message="Jobs are created when you create datasets, run DQ checks, or trigger compliance scans. Create a dataset to get started."
        action={{ label: 'Create Dataset', onClick: () => navigate('/datasets/create') }}
      />
    );
  }

  return (
    <div className="job-list-page">
      <div className="job-list-header">
        <h1>Jobs & Workflows</h1>
      </div>
      <div className="job-list-table">
        <table role="table" aria-label="Jobs list">
          <thead>
            <tr>
              <th scope="col">Type</th>
              <th scope="col">Status</th>
              <th scope="col">Resource</th>
              <th scope="col">Created</th>
              <th scope="col">Completed</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((job) => (
              <tr
                key={job.id}
                onClick={() => navigate(`/jobs/${job.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/jobs/${job.id}`);
                  }
                }}
                className="job-row"
                role="row"
                tabIndex={0}
                aria-label={`Job ${job.type} - ${job.status}`}
              >
                <td>{job.type}</td>
                <td>
                  <span
                    className={`status-badge status-${job.status.toLowerCase()}`}
                    aria-label={`Status: ${job.status}`}
                  >
                    {job.status}
                  </span>
                </td>
                <td>
                  {job.resource_type}: {job.resource_id.slice(0, 8)}...
                </td>
                <td>{new Date(job.created_at).toLocaleString()}</td>
                <td>{job.completed_at ? new Date(job.completed_at).toLocaleString() : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.total_pages > 1 && (
        <div className="job-list-pagination">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={!data.has_previous}>
            Previous
          </button>
          <span>
            Page {data.page} of {data.total_pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={!data.has_next}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
