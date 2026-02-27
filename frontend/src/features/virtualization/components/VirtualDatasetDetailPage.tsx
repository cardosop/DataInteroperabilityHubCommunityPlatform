/**
 * Virtual Dataset Detail Page
 * Displays dataset details with query execution UI
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useVirtualDataset, useDeleteVirtualDataset, useValidateVirtualDataset } from '../hooks/useVirtualization';
import { QueryExecutionUI } from './QueryExecutionUI';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './VirtualDatasetDetailPage.css';

export function VirtualDatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: dataset, isLoading, error, refetch } = useVirtualDataset(id);
  const deleteMutation = useDeleteVirtualDataset();
  const validateMutation = useValidateVirtualDataset();

  const handleDelete = async () => {
    if (!id || !confirm('Are you sure you want to delete this dataset? This action cannot be undone.')) return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/virtualization');
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleValidate = async () => {
    if (!id) return;
    try {
      const result = await validateMutation.mutateAsync(id);
      if (result.is_valid) {
        alert('Dataset validation passed!');
      } else {
        alert(`Validation failed: ${result.errors.join(', ')}`);
      }
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load dataset" onRetry={() => refetch()} />;
  }

  if (isLoading || !dataset) {
    return <LoadingSpinner message="Loading dataset..." />;
  }

  return (
    <div className="virtual-dataset-detail-page">
      <div className="virtual-dataset-detail-header">
        <button onClick={() => navigate('/virtualization')} className="btn-back" type="button">
          ← Back to Datasets
        </button>
        <div className="header-actions">
          <button onClick={handleValidate} className="btn-secondary" type="button" disabled={validateMutation.isPending}>
            {validateMutation.isPending ? 'Validating...' : 'Validate'}
          </button>
          <button onClick={() => navigate(`/virtualization/${id}/edit`)} className="btn-secondary" type="button">
            Edit
          </button>
          <button onClick={handleDelete} className="btn-danger" type="button" disabled={deleteMutation.isPending}>
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="virtual-dataset-detail-content">
        <div className="dataset-info-section">
          <h1>{dataset.name}</h1>
          {dataset.description && <p className="dataset-description">{dataset.description}</p>}
          
          <div className="dataset-metadata">
            <div className="metadata-item">
              <span className="metadata-label">Query Type:</span>
              <span className="query-type-badge">{dataset.query_type}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Status:</span>
              <span className={`status-badge status-${dataset.status.toLowerCase()}`}>
                {dataset.status}
              </span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Version:</span>
              <span>{dataset.version}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Created:</span>
              <span>{new Date(dataset.created_at).toLocaleString()}</span>
            </div>
          </div>

          {dataset.query && (
            <div className="dataset-query-section">
              <h2>Query</h2>
              <pre className="query-display">{dataset.query}</pre>
            </div>
          )}

          {dataset.schema && Object.keys(dataset.schema).length > 0 && (
            <div className="dataset-schema-section">
              <h2>Schema</h2>
              <pre className="schema-display">{JSON.stringify(dataset.schema, null, 2)}</pre>
            </div>
          )}
        </div>

        <div className="query-execution-section">
          <h2>Query Execution</h2>
          <QueryExecutionUI datasetId={id!} />
        </div>
      </div>
    </div>
  );
}
