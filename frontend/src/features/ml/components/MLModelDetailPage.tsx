/**
 * ML Model Detail Page
 * Route: /ml/models/:id
 */

import { useParams, useNavigate, Link } from 'react-router-dom';
import { useMLModel } from '../hooks/useML';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './MLModelDetailPage.css';

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '\u2014';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '\u2014';
  }
}

export function MLModelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: model, isLoading, error } = useMLModel(id ?? null);

  if (isLoading) return <LoadingSpinner message="Loading model..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load model" />;
  if (!model) return <ErrorDisplay error={new Error('Model not found')} title="Not Found" />;

  return (
    <div className="ml-detail-page">
      <button className="ml-back-btn" onClick={() => navigate('/ml')} type="button">
        &larr; Back to ML Platform
      </button>

      <div className="ml-detail-header">
        <div className="ml-detail-title-row">
          <h1>{model.odh_model_name}</h1>
          <span className={`status-badge status-${model.status.toLowerCase()}`}>
            {model.status}
          </span>
        </div>
        <p className="ml-detail-subtitle">
          Version {model.odh_model_version} &middot; {model.model_type}
        </p>
      </div>

      <div className="ml-detail-grid">
        <section className="ml-detail-card">
          <h2>Model Information</h2>
          <dl className="ml-detail-dl">
            <dt>ODH Model ID</dt>
            <dd className="monospace">{model.odh_model_id}</dd>
            <dt>Version</dt>
            <dd>{model.odh_model_version}</dd>
            <dt>Type</dt>
            <dd>{model.model_type}</dd>
            <dt>Status</dt>
            <dd>
              <span className={`status-badge status-${model.status.toLowerCase()}`}>
                {model.status}
              </span>
            </dd>
          </dl>
        </section>

        <section className="ml-detail-card">
          <h2>Linked Resources</h2>
          <dl className="ml-detail-dl">
            <dt>Asset</dt>
            <dd>
              {model.asset_id ? (
                <Link to={`/assets/${model.asset_id}`}>{model.asset_id.substring(0, 8)}...</Link>
              ) : '\u2014'}
            </dd>
            <dt>Contract</dt>
            <dd>
              {model.contract_id ? (
                <Link to={`/contracts/${model.contract_id}`}>{model.contract_id.substring(0, 8)}...</Link>
              ) : '\u2014'}
            </dd>
            <dt>Training Dataset</dt>
            <dd>
              {model.training_dataset_id ? (
                <Link to={`/datasets/${model.training_dataset_id}`}>{model.training_dataset_id.substring(0, 8)}...</Link>
              ) : '\u2014'}
            </dd>
            <dt>Training Job</dt>
            <dd>{model.training_job_id ? model.training_job_id.substring(0, 12) + '...' : '\u2014'}</dd>
          </dl>
        </section>

        <section className="ml-detail-card">
          <h2>Timestamps</h2>
          <dl className="ml-detail-dl">
            <dt>Created</dt>
            <dd>{formatDate(model.created_at)}</dd>
            <dt>Updated</dt>
            <dd>{formatDate(model.updated_at)}</dd>
          </dl>
        </section>
      </div>
    </div>
  );
}
