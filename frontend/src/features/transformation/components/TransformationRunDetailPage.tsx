/**
 * Transformation Run (Execution) Detail Page
 * Shows execution status, metrics, logs, and error info
 */

import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { useTransformationExecution } from '../hooks/useTransformationPipelines';
import './TransformationRunDetailPage.css';

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '\u2014';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '\u2014';
  }
}

export function TransformationRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, error } = useTransformationExecution(id ?? null);

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error) {
    return (
      <div className="transformation-run-detail-page">
        <ErrorDisplay error={error} title="Execution not found" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="transformation-run-detail-page">
        <ErrorDisplay
          error={new Error('Execution not found')}
          title="Execution not found"
        />
      </div>
    );
  }

  const metrics = data.metrics ?? {};
  const logEntries = data.execution_log ?? [];

  return (
    <div className="transformation-run-detail-page">
      <div className="transformation-run-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Transformations', href: '/transformation' },
            { label: 'Pipeline', href: `/transformation/pipelines/${data.pipeline}` },
            { label: `Execution ${id?.slice(0, 8) ?? ''}` },
          ]}
        />

        <div className="transformation-run-header">
          <h1>Execution Detail</h1>
          <Button
            variant="secondary"
            onClick={() => navigate(`/transformation/pipelines/${data.pipeline}`)}
          >
            Back to Pipeline
          </Button>
        </div>

        <div className="transformation-run-metadata">
          <span
            className={`status-badge status-${data.status.toLowerCase()}`}
            aria-label={`Status: ${data.status}`}
          >
            {data.status}
          </span>
          <span className="execution-mode-badge">{data.execution_mode}</span>
          <div className="run-uuid" data-testid="transformation-execution-uuid">
            <UuidWithCopy value={data.id} label="Execution ID" />
          </div>
        </div>

        <div className="transformation-run-info-grid">
          <div className="info-item">
            <span className="info-label">Pipeline</span>
            <span className="info-value"><code>{data.pipeline.slice(0, 8)}...</code></span>
          </div>
          <div className="info-item">
            <span className="info-label">Asset</span>
            <span className="info-value"><code>{data.asset.slice(0, 8)}...</code></span>
          </div>
          <div className="info-item">
            <span className="info-label">Started</span>
            <span className="info-value">{formatDateTime(data.started_at)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Completed</span>
            <span className="info-value">{formatDateTime(data.completed_at)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Created</span>
            <span className="info-value">{formatDateTime(data.created_at)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Updated</span>
            <span className="info-value">{formatDateTime(data.updated_at)}</span>
          </div>
        </div>

        {/* Error message */}
        {data.error_message && (
          <section className="transformation-run-error-section">
            <h2>Error</h2>
            <pre className="transformation-run-error-message">{data.error_message}</pre>
          </section>
        )}

        {/* Metrics */}
        {Object.keys(metrics).length > 0 && (
          <section className="transformation-run-metrics-section">
            <h2>Metrics</h2>
            <div className="transformation-run-metrics-grid">
              {Object.entries(metrics).map(([key, value]) => (
                <div key={key} className="metric-card">
                  <span className="metric-label">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                  <span className="metric-value">
                    {typeof value === 'number' ? value.toLocaleString() : String(value ?? '\u2014')}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Execution Log */}
        <section className="transformation-run-log-section">
          <h2>Execution Log ({logEntries.length})</h2>
          {logEntries.length === 0 ? (
            <p className="transformation-run-log-empty">No log entries.</p>
          ) : (
            <div className="transformation-run-log-list">
              {logEntries.map((entry, index) => (
                <div key={index} className="log-entry">
                  <pre className="log-entry-content">
                    {JSON.stringify(entry, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
