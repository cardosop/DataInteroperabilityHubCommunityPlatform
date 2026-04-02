/**
 * Training Dashboard Page
 * Route: /ml/training/:id
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useTrainingJob, useCancelTrainingJob } from '../hooks/useML';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { TrainingJobStatus } from '../../../shared/types/ml';
import './MLModelDetailPage.css';

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '\u2014';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '\u2014';
  }
}

export function TrainingDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: job, isLoading, error, refetch } = useTrainingJob(id ?? null);
  const cancelMutation = useCancelTrainingJob();

  if (isLoading) return <LoadingSpinner message="Loading training job..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load training job" />;
  if (!job) return <ErrorDisplay error={new Error('Training job not found')} title="Not Found" />;

  const isRunning = job.status === TrainingJobStatus.RUNNING || job.status === TrainingJobStatus.PENDING;

  const handleCancel = async () => {
    await cancelMutation.mutateAsync(job.id);
    refetch();
  };

  return (
    <div className="ml-detail-page">
      <button className="ml-back-btn" onClick={() => navigate('/ml')} type="button">
        &larr; Back to ML Platform
      </button>

      <div className="ml-detail-header">
        <div className="ml-detail-title-row">
          <h1>Training Job</h1>
          <span className={`status-badge status-${job.status.toLowerCase()}`}>
            {job.status}
          </span>
        </div>
        <p className="ml-detail-subtitle">Job {job.id}</p>
      </div>

      <div className="ml-detail-grid">
        <section className="ml-detail-card">
          <h2>Job Details</h2>
          <dl className="ml-detail-dl">
            <dt>Job ID</dt>
            <dd className="monospace">{job.id}</dd>
            <dt>Model ID</dt>
            <dd className="monospace">{job.model_id}</dd>
            <dt>Dataset ID</dt>
            <dd className="monospace">{job.dataset_id}</dd>
            <dt>Status</dt>
            <dd>
              <span className={`status-badge status-${job.status.toLowerCase()}`}>
                {job.status}
              </span>
            </dd>
          </dl>
        </section>

        <section className="ml-detail-card">
          <h2>Timeline</h2>
          <dl className="ml-detail-dl">
            <dt>Created</dt>
            <dd>{formatDate(job.created_at)}</dd>
            <dt>Started</dt>
            <dd>{formatDate(job.started_at)}</dd>
            <dt>Completed</dt>
            <dd>{formatDate(job.completed_at)}</dd>
          </dl>
        </section>

        {job.error_message && (
          <section className="ml-detail-card">
            <h2>Error</h2>
            <p className="ml-error-message">{job.error_message}</p>
          </section>
        )}

        {isRunning && (
          <section className="ml-detail-card">
            <h2>Actions</h2>
            <button
              type="button"
              className="ml-action-btn ml-action-btn-danger"
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Training'}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
