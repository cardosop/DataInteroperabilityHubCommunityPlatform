/**
 * Job Detail Page
 * Display job details with progress visualization
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useJob, useCancelJob } from '../hooks/useJobs';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './JobDetailPage.css';

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: job, isLoading, error, refetch } = useJob(id || null);
  const cancelMutation = useCancelJob();

  const handleCancel = async () => {
    if (!id || !confirm('Are you sure you want to cancel this job?')) return;
    try {
      await cancelMutation.mutateAsync(id);
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading job..." />;
  if (error || !job) {
    return <ErrorDisplay error={error || new Error('Job not found')} title="Failed to load job" onRetry={() => refetch()} />;
  }

  const isRunning = job.status === 'PENDING' || job.status === 'RUNNING';
  const progressPercentage = isRunning ? 50 : job.status === 'COMPLETED' ? 100 : 0;

  return (
    <div className="job-detail-page">
      <div className="job-detail-header">
        <button onClick={() => navigate('/jobs')} className="btn-back" type="button">
          ← Back to Jobs
        </button>
        <div className="job-detail-actions">
          {isRunning && (
            <button
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
              className="btn-danger"
              type="button"
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Job'}
            </button>
          )}
        </div>
      </div>

      <div className="job-detail-content">
        <div className="job-detail-main">
          <h1>Job: {job.type}</h1>

          <div className="job-status-section">
            <div className="status-header">
              <span className={`status-badge status-${job.status.toLowerCase()}`}>
                {job.status}
              </span>
              {isRunning && (
                <div className="progress-indicator">
                  <LoadingSpinner size="small" />
                  <span>Running...</span>
                </div>
              )}
            </div>

            {isRunning && (
              <div className="progress-bar-container">
                <div className="progress-bar">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${progressPercentage}%` }}
                  />
                </div>
                <span className="progress-text">{progressPercentage}%</span>
              </div>
            )}
          </div>

          <div className="job-detail-metadata">
            <div className="metadata-item">
              <label>Type</label>
              <span>{job.type}</span>
            </div>
            <div className="metadata-item">
              <label>Resource Type</label>
              <span>{job.resource_type}</span>
            </div>
            <div className="metadata-item">
              <label>Resource ID</label>
              <code>{job.resource_id}</code>
            </div>
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(job.created_at).toLocaleString()}</span>
            </div>
            {job.started_at && (
              <div className="metadata-item">
                <label>Started</label>
                <span>{new Date(job.started_at).toLocaleString()}</span>
              </div>
            )}
            {job.completed_at && (
              <div className="metadata-item">
                <label>Completed</label>
                <span>{new Date(job.completed_at).toLocaleString()}</span>
              </div>
            )}
          </div>

          {job.error_message && (
            <div className="job-error">
              <h3>Error</h3>
              <pre>{job.error_message}</pre>
            </div>
          )}

          {job.details_json && Object.keys(job.details_json).length > 0 && (
            <div className="job-details">
              <h3>Details</h3>
              <pre>{JSON.stringify(job.details_json, null, 2)}</pre>
            </div>
          )}

          {job.result_json && Object.keys(job.result_json).length > 0 && (
            <div className="job-results">
              <h3>Results</h3>
              <pre>{JSON.stringify(job.result_json, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>

      {cancelMutation.isError && (
        <ErrorDisplay error={cancelMutation.error} title="Failed to cancel job" onRetry={() => cancelMutation.reset()} />
      )}
    </div>
  );
}
