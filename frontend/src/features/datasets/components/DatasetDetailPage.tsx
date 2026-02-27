/**
 * Dataset Detail Page
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useDataset, useUpdateDataset, useDeleteDataset } from '../hooks/useDatasets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useState } from 'react';
import './DatasetDetailPage.css';

export function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: dataset, isLoading, error, refetch } = useDataset(id || null);
  const updateMutation = useUpdateDataset();
  const deleteMutation = useDeleteDataset();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({ name: '', description: '' });

  const handleEdit = () => {
    if (dataset) {
      setEditData({ name: dataset.name, description: dataset.description || '' });
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    if (!id) return;
    try {
      await updateMutation.mutateAsync({ id, data: editData });
      setIsEditing(false);
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleDelete = async () => {
    if (!id || !confirm('Are you sure you want to delete this dataset?')) return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/datasets');
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading dataset..." />;
  if (error || !dataset) {
    return <ErrorDisplay error={error || new Error('Dataset not found')} title="Failed to load dataset" onRetry={() => refetch()} />;
  }

  return (
    <div className="dataset-detail-page">
      <div className="dataset-detail-header">
        <button onClick={() => navigate('/datasets')} className="btn-back" type="button">
          ← Back to Datasets
        </button>
        <div className="dataset-detail-actions">
          {!isEditing ? (
            <>
              <button onClick={handleEdit} className="btn-secondary" type="button">Edit</button>
              <button onClick={handleDelete} className="btn-danger" disabled={deleteMutation.isPending} type="button">
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setIsEditing(false)} className="btn-secondary" type="button">Cancel</button>
              <button onClick={handleSave} className="btn-primary" disabled={updateMutation.isPending} type="button">
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="dataset-detail-content">
        {isEditing ? (
          <div className="dataset-edit-form">
            <div className="form-group">
              <label>Name</label>
              <input
                type="text"
                value={editData.name}
                onChange={(e) => setEditData({ ...editData, name: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea
                value={editData.description}
                onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                rows={4}
              />
            </div>
          </div>
        ) : (
          <>
            <h1>{dataset.name || 'Dataset'}</h1>
            {dataset.description && <p className="dataset-description">{dataset.description}</p>}

            <div className="dataset-detail-metadata">
              <div className="metadata-item">
                <label>Format</label>
                <span>{dataset.format}</span>
              </div>
              <div className="metadata-item">
                <label>Size</label>
                <span>{((dataset.size_bytes ?? 0) / 1024).toFixed(2)} KB</span>
              </div>
              {dataset.row_count && (
                <div className="metadata-item">
                  <label>Rows</label>
                  <span>{dataset.row_count.toLocaleString()}</span>
                </div>
              )}
              <div className="metadata-item">
                <label>Version</label>
                <span>{dataset.version}</span>
              </div>
              <div className="metadata-item">
                <label>Created</label>
                <span>{new Date(dataset.created_at).toLocaleString()}</span>
              </div>
              <div className="metadata-item">
                <label>Updated</label>
                <span>{new Date(dataset.updated_at).toLocaleString()}</span>
              </div>
            </div>

            {dataset.schema && dataset.schema.fields.length > 0 && (
              <div className="dataset-schema">
                <h2>Schema</h2>
                <table>
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Type</th>
                      <th>Nullable</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataset.schema.fields.map((field) => (
                      <tr key={field.name}>
                        <td><strong>{field.name}</strong></td>
                        <td>{field.type}</td>
                        <td>{field.nullable ? 'Yes' : 'No'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {updateMutation.isError && (
        <ErrorDisplay error={updateMutation.error} title="Failed to update dataset" onRetry={() => updateMutation.reset()} />
      )}
      {deleteMutation.isError && (
        <ErrorDisplay error={deleteMutation.error} title="Failed to delete dataset" onRetry={() => deleteMutation.reset()} />
      )}
    </div>
  );
}
