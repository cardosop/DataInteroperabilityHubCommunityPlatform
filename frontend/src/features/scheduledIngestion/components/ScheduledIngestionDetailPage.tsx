/**
 * Scheduled Ingestion Detail Page
 * Shows detailed information about a scheduled ingestion and its runs
 */

import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useDeleteScheduledIngestion,
  useScheduledIngestion,
  useScheduledIngestionRuns,
  useTriggerScheduledIngestion,
} from '../hooks/useScheduledIngestion';
import './ScheduledIngestionDetailPage.css';

export function ScheduledIngestionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: schedule, isLoading, error, refetch } = useScheduledIngestion(id || null);
  const { data: runs, isLoading: runsLoading } = useScheduledIngestionRuns(id || null);
  const triggerMutation = useTriggerScheduledIngestion();
  const deleteMutation = useDeleteScheduledIngestion();

  const handleTrigger = async () => {
    if (!id || !confirm('Are you sure you want to trigger this scheduled ingestion?')) return;
    try {
      await triggerMutation.mutateAsync({ id });
      refetch();
    } catch (err) {
      console.error('Trigger failed:', err);
    }
  };

  const handleDelete = async () => {
    if (
      !id ||
      !confirm(
        'Are you sure you want to delete this scheduled ingestion? This action cannot be undone.'
      )
    )
      return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/scheduled-ingestions');
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleEdit = () => {
    if (id) navigate(`/scheduled-ingestions/${id}/edit`);
  };

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load scheduled ingestion"
        onRetry={() => refetch()}
      />
    );
  }

  if (isLoading) {
    return <LoadingSpinner message="Loading scheduled ingestion..." />;
  }

  if (!schedule) {
    return (
      <EmptyState
        title="Scheduled ingestion not found"
        message="The requested scheduled ingestion could not be found."
        action={{
          label: 'Back to Scheduled Ingestion',
          onClick: () => navigate('/scheduled-ingestions'),
        }}
      />
    );
  }

  const canTrigger = schedule.status === 'ACTIVE';

  return (
    <div className="scheduled-ingestion-detail-page" data-testid="scheduled-ingestion-detail-page">
      <div className="scheduled-ingestion-detail-header">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => navigate('/scheduled-ingestions')}
          aria-label="Back to scheduled ingestions"
        >
          ← Back to Scheduled Ingestion
        </button>
        <div className="scheduled-ingestion-detail-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleEdit}
            aria-label="Edit scheduled ingestion"
          >
            Edit
          </button>
          {canTrigger && (
            <button
              type="button"
              className="btn-primary"
              onClick={handleTrigger}
              disabled={triggerMutation.isPending}
              aria-label="Trigger scheduled ingestion"
            >
              {triggerMutation.isPending ? 'Triggering...' : 'Trigger Now'}
            </button>
          )}
          <button
            type="button"
            className="btn-danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            aria-label="Delete scheduled ingestion"
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="scheduled-ingestion-detail-content">
        <div className="scheduled-ingestion-detail-section">
          <h2>Basic Information</h2>
          <dl className="scheduled-ingestion-detail-list">
            <dt>Name</dt>
            <dd>{schedule.name}</dd>
            <dt>Description</dt>
            <dd>{schedule.description || '—'}</dd>
            <dt>Status</dt>
            <dd>
              <span className={`scheduled-ingestion-status-badge ${schedule.status.toLowerCase()}`}>
                {schedule.status}
              </span>
            </dd>
            <dt>Source Type</dt>
            <dd>{schedule.source_type}</dd>
            <dt>Schedule Type</dt>
            <dd>{schedule.schedule_type}</dd>
            <dt>Next Run</dt>
            <dd>{schedule.next_run_at ? new Date(schedule.next_run_at).toLocaleString() : '—'}</dd>
            {schedule.error_message && (
              <>
                <dt>Error Message</dt>
                <dd className="error-message">{schedule.error_message}</dd>
              </>
            )}
          </dl>
        </div>

        {(schedule.asset_name || schedule.contract_name) && (
          <div className="scheduled-ingestion-detail-section">
            <h2>Associated Resources</h2>
            <dl className="scheduled-ingestion-detail-list">
              {schedule.asset_name && (
                <>
                  <dt>Asset</dt>
                  <dd>{schedule.asset_name}</dd>
                </>
              )}
              {schedule.contract_name && (
                <>
                  <dt>Contract</dt>
                  <dd>{schedule.contract_name}</dd>
                </>
              )}
            </dl>
          </div>
        )}

        <div className="scheduled-ingestion-detail-section">
          <h2>Runs</h2>
          {runsLoading ? (
            <LoadingSpinner message="Loading runs..." />
          ) : !runs || runs.length === 0 ? (
            <EmptyState title="No runs" message="No ingestion runs found for this schedule." />
          ) : (
            <table className="scheduled-ingestion-runs-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Completed</th>
                  <th>Files Processed</th>
                  <th>Datasets Created</th>
                  <th>Execution</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <span className={`run-status-badge ${run.status.toLowerCase()}`}>
                        {run.status}
                      </span>
                    </td>
                    <td>{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</td>
                    <td>{run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'}</td>
                    <td>{run.files_processed ?? '—'}</td>
                    <td>{run.datasets_created ?? '—'}</td>
                    <td>
                      {run.prefect_flow_run_id ? (
                        <span className="scheduled-ingestion-run-execution">
                          <span
                            className="execution-badge execution-prefect"
                            title="Executed by Prefect"
                          >
                            Prefect
                          </span>
                          {typeof import.meta.env.VITE_PREFECT_UI_BASE_URL === 'string' &&
                          import.meta.env.VITE_PREFECT_UI_BASE_URL ? (
                            <a
                              href={`${import.meta.env.VITE_PREFECT_UI_BASE_URL.replace(/\/$/, '')}/flow-runs/flow-run/${run.prefect_flow_run_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="link-prefect"
                              aria-label={`View run ${run.prefect_flow_run_id} in Prefect`}
                            >
                              View in Prefect
                            </a>
                          ) : (
                            <span className="run-prefect-id" title={run.prefect_flow_run_id}>
                              {run.prefect_flow_run_id}
                            </span>
                          )}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
