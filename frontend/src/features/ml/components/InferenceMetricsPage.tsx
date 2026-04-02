/**
 * Inference Metrics Page
 * Route: /ml/inference/:id
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useInferenceDeployment, useInferenceMetrics, useUndeployInference } from '../hooks/useML';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { InferenceDeploymentStatus } from '../../../shared/types/ml';
import './MLModelDetailPage.css';

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '\u2014';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '\u2014';
  }
}

export function InferenceMetricsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: deployment, isLoading, error, refetch } = useInferenceDeployment(id ?? null);
  const { data: metrics, isLoading: metricsLoading } = useInferenceMetrics(id ?? null);
  const undeployMutation = useUndeployInference();

  if (isLoading) return <LoadingSpinner message="Loading deployment..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load deployment" />;
  if (!deployment) return <ErrorDisplay error={new Error('Deployment not found')} title="Not Found" />;

  const isDeployed = deployment.status === InferenceDeploymentStatus.DEPLOYED;

  const handleUndeploy = async () => {
    await undeployMutation.mutateAsync(deployment.id);
    refetch();
  };

  return (
    <div className="ml-detail-page">
      <button className="ml-back-btn" onClick={() => navigate('/ml')} type="button">
        &larr; Back to ML Platform
      </button>

      <div className="ml-detail-header">
        <div className="ml-detail-title-row">
          <h1>Inference Deployment</h1>
          <span className={`status-badge status-${deployment.status.toLowerCase()}`}>
            {deployment.status}
          </span>
        </div>
        <p className="ml-detail-subtitle">Deployment {deployment.id}</p>
      </div>

      <div className="ml-detail-grid">
        <section className="ml-detail-card">
          <h2>Deployment Info</h2>
          <dl className="ml-detail-dl">
            <dt>Deployment ID</dt>
            <dd className="monospace">{deployment.id}</dd>
            <dt>Model ID</dt>
            <dd className="monospace">{deployment.model_id}</dd>
            <dt>Status</dt>
            <dd>
              <span className={`status-badge status-${deployment.status.toLowerCase()}`}>
                {deployment.status}
              </span>
            </dd>
            <dt>Replicas</dt>
            <dd>{deployment.replicas ?? '\u2014'}</dd>
            <dt>Endpoint</dt>
            <dd>
              {deployment.endpoint ? (
                <a href={deployment.endpoint} target="_blank" rel="noopener noreferrer">
                  {deployment.endpoint}
                </a>
              ) : '\u2014'}
            </dd>
            <dt>Created</dt>
            <dd>{formatDate(deployment.created_at)}</dd>
          </dl>
        </section>

        <section className="ml-detail-card">
          <h2>Performance Metrics</h2>
          {metricsLoading ? (
            <p className="ml-text-muted">Loading metrics...</p>
          ) : metrics ? (
            <div className="ml-metrics-grid">
              <div className="ml-metric-item">
                <span className="ml-metric-value">{metrics.total_requests.toLocaleString()}</span>
                <span className="ml-metric-label">Total Requests</span>
              </div>
              <div className="ml-metric-item">
                <span className="ml-metric-value">{metrics.successful_requests.toLocaleString()}</span>
                <span className="ml-metric-label">Successful</span>
              </div>
              <div className="ml-metric-item">
                <span className="ml-metric-value">{metrics.failed_requests.toLocaleString()}</span>
                <span className="ml-metric-label">Failed</span>
              </div>
              <div className="ml-metric-item">
                <span className="ml-metric-value">{metrics.error_rate.toFixed(1)}%</span>
                <span className="ml-metric-label">Error Rate</span>
              </div>
              <div className="ml-metric-item">
                <span className="ml-metric-value">{metrics.average_latency_ms?.toFixed(0) ?? '\u2014'} ms</span>
                <span className="ml-metric-label">Avg Latency</span>
              </div>
              {metrics.accuracy != null && (
                <div className="ml-metric-item">
                  <span className="ml-metric-value">{(metrics.accuracy * 100).toFixed(1)}%</span>
                  <span className="ml-metric-label">Accuracy</span>
                </div>
              )}
            </div>
          ) : (
            <p className="ml-text-muted">No metrics available yet.</p>
          )}
        </section>

        {isDeployed && (
          <section className="ml-detail-card">
            <h2>Actions</h2>
            <button
              type="button"
              className="ml-action-btn ml-action-btn-danger"
              onClick={handleUndeploy}
              disabled={undeployMutation.isPending}
            >
              {undeployMutation.isPending ? 'Undeploying...' : 'Undeploy'}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
