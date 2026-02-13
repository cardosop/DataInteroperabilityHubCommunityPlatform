/**
 * Compliance Run Detail Page
 * Displays compliance run details with results viewer
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useComplianceRun, useComplianceRunResults } from '../hooks/useCompliance';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ComplianceRunResultsViewer } from './ComplianceRunResultsViewer';
import './ComplianceRunDetailPage.css';

export function ComplianceRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: complianceRun, isLoading, error, refetch } = useComplianceRun(id || null);
  const {
    data: results,
    isLoading: resultsLoading,
    error: resultsError,
  } = useComplianceRunResults(id || null);

  if (isLoading) {
    return <LoadingSpinner message="Loading compliance run..." />;
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

  const isRunning = complianceRun.status === 'PENDING' || complianceRun.status === 'RUNNING';

  return (
    <div className="compliance-run-detail-page">
      <div className="compliance-run-detail-header">
        <button onClick={() => navigate('/compliance')} className="btn-back" type="button">
          ← Back to Compliance Runs
        </button>
      </div>

      <div className="compliance-run-detail-content">
        <div className="compliance-run-detail-main">
          <h1>Compliance Run</h1>

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

            {complianceRun.allowed_to_store !== undefined && (
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
    </div>
  );
}
