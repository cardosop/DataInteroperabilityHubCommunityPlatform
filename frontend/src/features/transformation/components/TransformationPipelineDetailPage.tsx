/**
 * Transformation Pipeline Detail Page
 * Displays pipeline detail; shows error when pipeline not found (404)
 */

import { useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useTransformationPipeline } from '../hooks/useTransformationPipelines';
import './TransformationPipelineDetailPage.css';

export function TransformationPipelineDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useTransformationPipeline(id ?? null);

  if (isLoading) {
    return <LoadingSpinner message="Loading pipeline..." />;
  }

  if (error) {
    return (
      <div className="transformation-detail-page">
        <ErrorDisplay
          error={error}
          title="Pipeline not found"
        />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="transformation-detail-page">
        <ErrorDisplay
          error={new Error('Pipeline not found')}
          title="Pipeline not found"
        />
      </div>
    );
  }

  return (
    <div className="transformation-detail-page">
      <div className="transformation-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Transformations', href: '/transformation' },
            { label: data.name || 'Pipeline' },
          ]}
        />
        <h1>{data.name}</h1>
        <div className="transformation-detail-metadata">
          <span
            className={`status-badge status-${(data.status || 'placeholder').toLowerCase()}`}
            aria-label={`Status: ${data.status}`}
          >
            {data.status}
          </span>
          <div className="pipeline-uuid" data-testid="transformation-pipeline-uuid">
            <UuidWithCopy value={data.id} label="Pipeline ID" />
          </div>
        </div>
      </div>
    </div>
  );
}
