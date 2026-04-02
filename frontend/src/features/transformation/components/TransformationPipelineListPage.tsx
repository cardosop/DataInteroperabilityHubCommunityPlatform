/**
 * Transformation Pipeline List Page
 * Displays list of transformation pipelines with filters and search
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useTransformationPipelines } from '../hooks/useTransformationPipelines';
import { PipelineStatus } from '../../../shared/types/transformation';
import type { TransformationListFilters } from '../../../shared/types/transformation';
import './TransformationPipelineListPage.css';
import { Button } from '../../../shared/components/Button';

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: PipelineStatus.DRAFT, label: 'Draft' },
  { value: PipelineStatus.ACTIVE, label: 'Active' },
  { value: PipelineStatus.INACTIVE, label: 'Inactive' },
  { value: PipelineStatus.ARCHIVED, label: 'Archived' },
];

export function TransformationPipelineListPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [search, setSearch] = useState('');

  const filters: TransformationListFilters = {};
  if (statusFilter) filters.status = statusFilter as PipelineStatus;
  if (search.trim()) filters.search = search.trim();

  const { data, isLoading, error, refetch } = useTransformationPipelines(filters);

  const handleCreatePipeline = () => {
    navigate('/transformation/create');
  };

  if (isLoading) {
    return <ListPageSkeleton />;
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
          <Button variant="primary" onClick={handleCreatePipeline}>
            Create Pipeline
          </Button>
        </div>
      </div>
    );
  }

  const hasFilters = !!statusFilter || !!search.trim();

  if (!data || (data.results.length === 0 && !hasFilters)) {
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
        <Button variant="primary" onClick={handleCreatePipeline}>
          Create Pipeline
        </Button>
      </div>

      <div className="transformation-list-filters">
        <input
          type="text"
          className="transformation-search-input"
          placeholder="Search pipelines..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search pipelines"
        />
        <select
          className="transformation-status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {data.results.length === 0 ? (
        <div className="transformation-no-results">
          <p>No pipelines match your filters.</p>
        </div>
      ) : (
        <div className="transformation-list-table">
          <table role="table" aria-label="Transformation pipelines list">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Description</th>
                <th scope="col">Status</th>
                <th scope="col">Version</th>
                <th scope="col">Steps</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((pipeline) => {
                const stepCount = pipeline.pipeline_definition?.steps?.length ?? 0;
                return (
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
                    role="button"
                    tabIndex={0}
                    aria-label={`Pipeline ${pipeline.name}`}
                  >
                    <td>
                      <strong>{pipeline.name}</strong>
                    </td>
                    <td className="pipeline-description-cell">
                      {pipeline.description || <span className="text-muted">No description</span>}
                    </td>
                    <td>
                      <span
                        className={`status-badge status-${(pipeline.status || 'draft').toLowerCase()}`}
                        aria-label={`Status: ${pipeline.status}`}
                      >
                        {pipeline.status}
                      </span>
                    </td>
                    <td>
                      <code>{pipeline.version || '1.0.0'}</code>
                    </td>
                    <td>{stepCount}</td>
                    <td className="pipeline-date-cell">
                      {pipeline.created_at
                        ? new Date(pipeline.created_at).toLocaleDateString()
                        : '\u2014'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
