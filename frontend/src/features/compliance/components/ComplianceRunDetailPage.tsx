/**
 * Compliance Run Detail Page
 * Displays compliance run details with results viewer
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useComplianceRun, useComplianceRunResults, useCancelComplianceRun, useDeleteComplianceRun } from '../hooks/useCompliance';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ComplianceRunResultsViewer } from './ComplianceRunResultsViewer';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import './ComplianceRunDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function ComplianceRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: complianceRun, isLoading, error, refetch } = useComplianceRun(id || null);
  const cancelMutation = useCancelComplianceRun();
  const deleteMutation = useDeleteComplianceRun();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const {
    data: results,
    isLoading: resultsLoading,
    error: resultsError,
  } = useComplianceRunResults(id || null);

  // Run is "stuck" if PENDING for >2 min with no started_at (worker never picked up the job).
  // Date.now() is called inside useEffect to satisfy react-hooks/purity.
  const [isStuckPending, setIsStuckPending] = useState(false);
  useEffect(() => {
    if (!complianceRun) { setIsStuckPending(false); return; }
    const createdMs = complianceRun.created_at
      ? new Date(complianceRun.created_at).getTime()
      : 0;
    const stuckThresholdMs = 2 * 60 * 1000;
    setIsStuckPending(
      complianceRun.status === 'PENDING' &&
      !complianceRun.started_at &&
      createdMs > 0 &&
      Date.now() - createdMs > stuckThresholdMs
    );
  }, [complianceRun]);

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error || !complianceRun) {
    return (
      <ErrorDisplay
        error={error || new Error('Compliance run not found')}
        title="Failed to load compliance run"
        onRetry={() => refetch()}
      />
    );
  }

  const isRunning = complianceRun.status === 'PENDING' || complianceRun.status === 'QUEUED' || complianceRun.status === 'RUNNING';

  const handleCancelClick = () => setShowCancelConfirm(true);
  const handleCancelConfirm = async () => {
    if (!id) return;
    setShowCancelConfirm(false);
    try {
      await cancelMutation.mutateAsync(id);
      toast.success('Compliance run cancelled.');
      refetch();
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to cancel compliance run');
    }
  };

  const handleDeleteClick = () => setShowDeleteConfirm(true);
  const handleDeleteConfirm = async () => {
    if (!id) return;
    setShowDeleteConfirm(false);
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('Compliance run deleted.');
      navigate('/compliance');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to delete compliance run');
    }
  };

  return (
    <div className="compliance-run-detail-page">
      <div className="compliance-run-detail-header">
        <Button onClick={() => navigate('/compliance')} variant="ghost">
          ← Back to Compliance Runs
        </Button>
        <div className="compliance-run-detail-actions">
          {isRunning && (
            <Button
 onClick={handleCancelClick}
 loading={cancelMutation.isPending}
 variant="danger">
              Cancel Run
            </Button>
          )}
          <Button
 onClick={handleDeleteClick}
 loading={deleteMutation.isPending}
 variant="danger">
            Delete
          </Button>
        </div>
      </div>

      <div className="compliance-run-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Compliance Runs', href: '/compliance' },
            { label: id ? `Run ${id.slice(0, 8)}` : 'Run' },
          ]}
        />
        <div className="compliance-run-detail-main">
          <h1>Compliance Run</h1>
          {id && (
            <div className="compliance-run-uuid" data-testid="compliance-run-uuid">
              <UuidWithCopy value={id} label="Compliance Run ID" />
            </div>
          )}

          <div className="compliance-run-status-section">
            <div className="status-header">
              <span className={`status-badge status-${complianceRun.status.toLowerCase()}`}>
                {complianceRun.status}
              </span>
              {complianceRun.overall_status && (
                <span
                  className={`overall-status-badge overall-status-${complianceRun.overall_status.toLowerCase()}`}
                >
                  {complianceRun.overall_status}
                </span>
              )}
              {complianceRun.risk_level && (
                <span className={`risk-level-badge risk-level-${complianceRun.risk_level.toLowerCase()}`}>
                  {complianceRun.risk_level}
                </span>
              )}
              {isRunning && (
                <div className="progress-indicator">
                  <LoadingSpinner size="small" />
                  <span>Running...</span>
                </div>
              )}
            </div>

            {isStuckPending && (
              <div className="compliance-run-stuck-hint" role="alert">
                <strong>Job may not have started.</strong> This run has been queued for over 2 minutes
                without starting. Ensure the <strong>RQ worker</strong> service is running (e.g.{' '}
                <code>worker-service</code> in Docker Compose). Check API logs for enqueue errors.
              </div>
            )}

            {!isRunning && complianceRun.allowed_to_store !== undefined && (
              <div className="allowed-to-store-display">
                <span className={`allowed-badge ${complianceRun.allowed_to_store ? 'allowed' : 'blocked'}`}>
                  {complianceRun.allowed_to_store ? '✓ Allowed to Store' : '✗ Blocked from Storage'}
                </span>
                {!complianceRun.allowed_to_store && (
                  <div className="blocked-warning">
                    <strong>Fail-Closed:</strong> This data cannot be stored due to compliance violations.
                    Please review the results and remediate issues before retrying.
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="compliance-run-detail-metadata">
            {complianceRun.regulations && complianceRun.regulations.length > 0 && (
              <div className="metadata-item">
                <label>Regulations</label>
                <span>{complianceRun.regulations.join(', ')}</span>
              </div>
            )}
            {complianceRun.asset && (
              <div className="metadata-item">
                <label>Asset</label>
                <code>{complianceRun.asset}</code>
              </div>
            )}
            {complianceRun.dataset && (
              <div className="metadata-item">
                <label>Dataset</label>
                <code>{complianceRun.dataset}</code>
              </div>
            )}
            {complianceRun.file && (
              <div className="metadata-item">
                <label>File</label>
                <code>{complianceRun.file}</code>
              </div>
            )}
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(complianceRun.created_at).toLocaleString()}</span>
            </div>
            {complianceRun.started_at && (
              <div className="metadata-item">
                <label>Started</label>
                <span>{new Date(complianceRun.started_at).toLocaleString()}</span>
              </div>
            )}
            {complianceRun.completed_at && (
              <div className="metadata-item">
                <label>Completed</label>
                <span>{new Date(complianceRun.completed_at).toLocaleString()}</span>
              </div>
            )}
          </div>

          {complianceRun.status === 'SUCCEEDED' && (
            <div className="compliance-run-results-section">
              <h2>Results</h2>
              {resultsLoading ? (
                <LoadingSpinner message="Loading results..." />
              ) : resultsError ? (
                <ErrorDisplay
                  error={resultsError}
                  title="Failed to load results"
                  onRetry={() => window.location.reload()}
                />
              ) : results ? (
                <ComplianceRunResultsViewer results={results} />
              ) : null}
            </div>
          )}

          {complianceRun.status === 'FAILED' && complianceRun.regulation_mapping_json && (
            <div className="compliance-run-error">
              <h3>Error</h3>
              <pre>{JSON.stringify(complianceRun.regulation_mapping_json, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
      <ConfirmDialog
        isOpen={showCancelConfirm}
        onClose={() => setShowCancelConfirm(false)}
        onConfirm={handleCancelConfirm}
        title="Cancel compliance run"
        message="Are you sure you want to cancel this compliance run? The job will be stopped."
        confirmLabel="Cancel Run"
        variant="warning"
      />
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
        title="Delete compliance run"
        message="Are you sure you want to delete this compliance run? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
