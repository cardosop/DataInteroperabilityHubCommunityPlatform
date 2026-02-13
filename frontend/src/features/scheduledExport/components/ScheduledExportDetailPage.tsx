/**
 * Scheduled Export Detail Page
 * Shows detailed information about a scheduled export and its runs
 */

import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useDeleteScheduledExport,
  useScheduledExport,
  useScheduledExportRuns,
  useTriggerScheduledExport,
} from '../hooks/useScheduledExport';
import './ScheduledExportDetailPage.css';

export function ScheduledExportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: export_, isLoading, error, refetch } = useScheduledExport(id || null);
  const { data: runs, isLoading: runsLoading } = useScheduledExportRuns(id || null);
  const triggerMutation = useTriggerScheduledExport();
  const deleteMutation = useDeleteScheduledExport();

  const handleTrigger = async () => {
    if (!id || !confirm('Are you sure you want to trigger this scheduled export?')) return;
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
        'Are you sure you want to delete this scheduled export? This action cannot be undone.'
      )
    )
      return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/scheduled-exports');
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleEdit = () => {
    if (id) navigate(`/scheduled-exports/${id}/edit`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading scheduled export..." />;
  }

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load scheduled export"
        onRetry={() => refetch()}
      />
    );
  }

  if (!export_) {
    return (
      <EmptyState
        title="Scheduled export not found"
        message="The requested scheduled export could not be found."
        action={{
          label: 'Back to Scheduled Exports',
          onClick: () => navigate('/scheduled-exports'),
        }}
      />
    );
  }

  const canTrigger = export_.status === 'ACTIVE';

  return (
    <div className="scheduled-export-detail-page" data-testid="scheduled-export-detail-page">
      <div className="scheduled-export-detail-header">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => navigate('/scheduled-exports')}
          aria-label="Back to scheduled exports"
        >
          ← Back to Scheduled Exports
        </button>
        <div className="scheduled-export-detail-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleEdit}
            aria-label="Edit scheduled export"
          >
            Edit
          </button>
          {canTrigger && (
            <button
              type="button"
              className="btn-primary"
              onClick={handleTrigger}
              disabled={triggerMutation.isPending}
              aria-label="Trigger scheduled export"
            >
              {triggerMutation.isPending ? 'Triggering...' : 'Trigger Now'}
            </button>
          )}
          <button
            type="button"
            className="btn-danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            aria-label="Delete scheduled export"
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="scheduled-export-detail-content">
        <div className="scheduled-export-detail-section">
          <h2>Basic Information</h2>
          <dl className="scheduled-export-detail-list">
            <dt>Name</dt>
            <dd>{export_.name}</dd>
            <dt>Status</dt>
            <dd>
              <span className={`scheduled-export-status-badge ${export_.status.toLowerCase()}`}>
                {export_.status}
              </span>
            </dd>
            <dt>Destination Type</dt>
            <dd>{export_.destination_type}</dd>
            <dt>Schedule</dt>
            <dd>{export_.schedule_config.cron}</dd>
            {export_.schedule_config.timezone && (
              <>
                <dt>Timezone</dt>
                <dd>{export_.schedule_config.timezone}</dd>
              </>
            )}
            <dt>Next Run</dt>
            <dd>{export_.next_run_at ? new Date(export_.next_run_at).toLocaleString() : '—'}</dd>
            <dt>Last Run</dt>
            <dd>{export_.last_run_at ? new Date(export_.last_run_at).toLocaleString() : '—'}</dd>
            {export_.last_run_status && (
              <>
                <dt>Last Run Status</dt>
                <dd>
                  <span className={`run-status-badge ${export_.last_run_status.toLowerCase()}`}>
                    {export_.last_run_status}
                  </span>
                </dd>
              </>
            )}
          </dl>
        </div>

        <div className="scheduled-export-detail-section">
          <h2>Source Scope</h2>
          <dl className="scheduled-export-detail-list">
            {export_.source_scope.asset_ids && export_.source_scope.asset_ids.length > 0 && (
              <>
                <dt>Asset IDs</dt>
                <dd>{export_.source_scope.asset_ids.join(', ')}</dd>
              </>
            )}
            {export_.source_scope.dataset_ids && export_.source_scope.dataset_ids.length > 0 && (
              <>
                <dt>Dataset IDs</dt>
                <dd>{export_.source_scope.dataset_ids.join(', ')}</dd>
              </>
            )}
            {export_.source_scope.file_ids && export_.source_scope.file_ids.length > 0 && (
              <>
                <dt>File IDs</dt>
                <dd>{export_.source_scope.file_ids.join(', ')}</dd>
              </>
            )}
            {export_.source_scope.contract_id && (
              <>
                <dt>Contract ID</dt>
                <dd>{export_.source_scope.contract_id}</dd>
              </>
            )}
            {!export_.source_scope.asset_ids?.length &&
              !export_.source_scope.dataset_ids?.length &&
              !export_.source_scope.file_ids?.length &&
              !export_.source_scope.contract_id && <dd>No source scope defined</dd>}
          </dl>
        </div>

        <div className="scheduled-export-detail-section">
          <h2>Runs</h2>
          {runsLoading ? (
            <LoadingSpinner message="Loading runs..." />
          ) : !runs || runs.length === 0 ? (
            <EmptyState title="No runs" message="No export runs found for this schedule." />
          ) : (
            <table className="scheduled-export-runs-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Completed</th>
                  <th>Items Found</th>
                  <th>Items Exported</th>
                  <th>Items Failed</th>
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
                    <td>{run.items_found ?? '—'}</td>
                    <td>{run.items_exported ?? '—'}</td>
                    <td>{run.items_failed ?? '—'}</td>
                    <td>
                      {run.prefect_flow_run_id ? (
                        <span className="scheduled-export-run-execution">
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
