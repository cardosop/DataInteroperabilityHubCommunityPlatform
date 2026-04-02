/**
 * Job Detail Page
 * Display job details with progress visualization
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useJob, useCancelJob } from '../hooks/useJobs';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './JobDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: job, isLoading, error, refetch } = useJob(id || null);
  const cancelMutation = useCancelJob();
  const toast = useToast();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const handleCancelClick = () => setShowCancelConfirm(true);
  const handleCancelConfirm = async () => {
    if (!id) return;
    setShowCancelConfirm(false);
    try {
      await cancelMutation.mutateAsync(id);
      toast.success('Job cancelled.');
      refetch();
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to cancel job');
    }
  };

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load job" onRetry={() => refetch()} />;
  }

  if (isLoading || !job) {
    return <DetailPageSkeleton />;
  }

  const isRunning = job.status === 'PENDING' || job.status === 'RUNNING';
  const progressPercentage = isRunning ? 50 : job.status === 'COMPLETED' ? 100 : 0;

  return (
    <div className="job-detail-page">
      <div className="job-detail-header">
        <Button onClick={() => navigate('/jobs')} variant="ghost">
          ← Back to Jobs
        </Button>
        <div className="job-detail-actions">
          {isRunning && (
            <Button
 onClick={handleCancelClick}
 loading={cancelMutation.isPending}
 variant="danger">
              Cancel Job
            </Button>
          )}
        </div>
      </div>

      <div className="job-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Jobs', href: '/jobs' },
            { label: job.type || 'Job' },
          ]}
        />
        <div className="job-detail-main">
          <h1>Job: {job.type}</h1>
          {id && (
            <div className="job-uuid" data-testid="job-uuid">
              <UuidWithCopy value={id} label="Job ID" />
            </div>
          )}

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

      <ConfirmDialog
        isOpen={showCancelConfirm}
        onClose={() => setShowCancelConfirm(false)}
        onConfirm={handleCancelConfirm}
        title="Cancel job"
        message="Are you sure you want to cancel this job?"
        confirmLabel="Cancel Job"
        variant="warning"
      />
    </div>
  );
}
