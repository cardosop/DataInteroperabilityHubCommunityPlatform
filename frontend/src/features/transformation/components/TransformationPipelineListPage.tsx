/**
 * Transformation Pipeline List Page
 * Displays list of transformation pipelines (placeholder API)
 */

import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useTransformationPipelines } from '../hooks/useTransformationPipelines';
import './TransformationPipelineListPage.css';

export function TransformationPipelineListPage() {
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useTransformationPipelines();

  const handleCreatePipeline = () => {
    navigate('/transformation/create');
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading transformation pipelines..." />;
  }

  if (error) {
    return (
      <div className="transformation-list-error-wrapper">
        <ErrorDisplay
          error={error}
          title="Failed to load transformation pipelines"
          onRetry={() => refetch()}
        />
        <div className="transformation-list-error-actions">
          <button className="btn-primary" onClick={handleCreatePipeline} type="button">
            Create Pipeline
          </button>
        </div>
      </div>
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        title="No transformation pipelines"
        message="Get started by creating your first transformation pipeline."
        action={{ label: 'Create Pipeline', onClick: handleCreatePipeline }}
      />
    );
  }

  return (
    <div className="transformation-pipeline-list-page">
      <div className="transformation-list-header">
        <h1>Transformation Pipelines</h1>
        <button className="btn-primary" onClick={handleCreatePipeline} type="button">
          Create Pipeline
        </button>
      </div>
      <div className="transformation-list-table">
        <table role="table" aria-label="Transformation pipelines list">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Status</th>
              <th scope="col">ID</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((pipeline) => (
              <tr
                key={pipeline.id}
                data-pipeline-id={pipeline.id}
                onClick={() => navigate(`/transformation/pipelines/${pipeline.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/transformation/pipelines/${pipeline.id}`);
                  }
                }}
                className="pipeline-row"
                role="row"
                tabIndex={0}
                aria-label={`Pipeline ${pipeline.name}`}
              >
                <td>
                  <strong>{pipeline.name}</strong>
                </td>
                <td>
                  <span
                    className={`status-badge status-${(pipeline.status || 'placeholder').toLowerCase()}`}
                    aria-label={`Status: ${pipeline.status}`}
                  >
                    {pipeline.status}
                  </span>
                </td>
                <td>
                  <code>{pipeline.id.slice(0, 8)}...</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
