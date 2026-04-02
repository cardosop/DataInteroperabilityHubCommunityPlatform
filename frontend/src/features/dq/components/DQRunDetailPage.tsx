/**
 * DQ Run Detail Page
 * Displays DQ run details with results viewer
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useDQRun, useDQRunResults } from '../hooks/useDQ';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DQRunResultsViewer } from './DQRunResultsViewer';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './DQRunDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function DQRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: dqRun, isLoading, error, refetch } = useDQRun(id || null);
  const {
    data: results,
    isLoading: resultsLoading,
    error: resultsError,
  } = useDQRunResults(id || null);

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error || !dqRun) {
    return (
      <ErrorDisplay
        error={error || new Error('DQ run not found')}
        title="Failed to load DQ run"
        onRetry={() => refetch()}
      />
    );
  }

  const isRunning = dqRun.status === 'PENDING' || dqRun.status === 'RUNNING';

  return (
    <div className="dq-run-detail-page">
      <div className="dq-run-detail-header">
        <Button onClick={() => navigate('/dq')} variant="ghost">
          ← Back to DQ Runs
        </Button>
      </div>

      <div className="dq-run-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'DQ Runs', href: '/dq' },
            { label: dqRun.profile_key || 'Run' },
          ]}
        />
        <div className="dq-run-detail-main">
          <h1>DQ Run: {dqRun.profile_key}</h1>
          {id && (
            <div className="dq-run-uuid" data-testid="dq-run-uuid">
              <UuidWithCopy value={id} label="DQ Run ID" />
            </div>
          )}

          <div className="dq-run-status-section">
            <div className="status-header">
              <span className={`status-badge status-${dqRun.status.toLowerCase()}`}>
                {dqRun.status}
              </span>
              {dqRun.overall_status && (
                <span
                  className={`overall-status-badge overall-status-${dqRun.overall_status.toLowerCase()}`}
                >
                  {dqRun.overall_status}
                </span>
              )}
              {isRunning && (
                <div className="progress-indicator">
                  <LoadingSpinner size="small" />
                  <span>Running...</span>
                </div>
              )}
            </div>

            {dqRun.quality_score !== null && dqRun.quality_score !== undefined && (
              <div className="quality-score-display">
                <span className="quality-score-label">Quality Score:</span>
                <span className="quality-score-value">
                  {Math.round(dqRun.quality_score * 100)}%
                </span>
              </div>
            )}
          </div>

          <div className="dq-run-detail-metadata">
            <div className="metadata-item">
              <label>Profile Key</label>
              <span>{dqRun.profile_key}</span>
            </div>
            <div className="metadata-item">
              <label>Engine</label>
              <span>{dqRun.engine}</span>
            </div>
            {dqRun.asset && (
              <div className="metadata-item">
                <label>Asset</label>
                <code>{dqRun.asset}</code>
              </div>
            )}
            {dqRun.dataset && (
              <div className="metadata-item">
                <label>Dataset</label>
                <code>{dqRun.dataset}</code>
              </div>
            )}
            {dqRun.file && (
              <div className="metadata-item">
                <label>File</label>
                <code>{dqRun.file}</code>
              </div>
            )}
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(dqRun.created_at).toLocaleString()}</span>
            </div>
            {dqRun.started_at && (
              <div className="metadata-item">
                <label>Started</label>
                <span>{new Date(dqRun.started_at).toLocaleString()}</span>
              </div>
            )}
            {dqRun.completed_at && (
              <div className="metadata-item">
                <label>Completed</label>
                <span>{new Date(dqRun.completed_at).toLocaleString()}</span>
              </div>
            )}
          </div>

          {dqRun.status === 'SUCCEEDED' && (
            <div className="dq-run-results-section">
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
                <DQRunResultsViewer results={results} />
              ) : null}
            </div>
          )}

          {dqRun.status === 'FAILED' && dqRun.details_json && (
            <div className="dq-run-error">
              <h3>Error</h3>
              <pre>{JSON.stringify(dqRun.details_json, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
