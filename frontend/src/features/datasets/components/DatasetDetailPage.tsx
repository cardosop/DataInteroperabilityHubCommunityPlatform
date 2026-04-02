/**
 * Dataset Detail Page
 */

import { useParams, useNavigate, Link } from 'react-router-dom';
import { useDataset, useUpdateDataset, useDeleteDataset } from '../hooks/useDatasets';
import { AssetPicker } from '../../../shared/components/pickers';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useState } from 'react';
import './DatasetDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: dataset, isLoading, error, refetch } = useDataset(id || null);
  const updateMutation = useUpdateDataset();
  const deleteMutation = useDeleteDataset();
  const toast = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [editData, setEditData] = useState<{ asset_id: string | null }>({ asset_id: null });

  const handleEdit = () => {
    if (dataset) {
      const aid = dataset.asset_id || dataset.asset || null;
      setEditData({
        asset_id: aid ? String(aid) : null,
      });
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    if (!id) return;
    const assetValue = editData.asset_id?.trim() || null;
    try {
      await updateMutation.mutateAsync({
        id,
        data: {
          asset_id: assetValue,
        },
      });
      setIsEditing(false);
      refetch();
      toast.success('Dataset updated successfully.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to update dataset');
      // ErrorDisplay also shown when updateMutation.isError
    }
  };

  const handleDeleteClick = () => setShowDeleteConfirm(true);
  const handleDeleteConfirm = async () => {
    if (!id) return;
    setShowDeleteConfirm(false);
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('Dataset deleted.');
      navigate('/datasets');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to delete dataset');
      // ErrorDisplay also shown when deleteMutation.isError
    }
  };

  if (isLoading) return <DetailPageSkeleton />;
  if (error || !dataset) {
    return <ErrorDisplay error={error || new Error('Dataset not found')} title="Failed to load dataset" onRetry={() => refetch()} />;
  }

  return (
    <div className="dataset-detail-page">
      <div className="dataset-detail-header">
        <Button onClick={() => navigate('/datasets')} variant="ghost">
          ← Back to Datasets
        </Button>
        <div className="dataset-detail-actions">
          {!isEditing ? (
            <>
              <Button onClick={handleEdit} variant="secondary">Edit</Button>
              {!(dataset.asset_id || dataset.asset) && (
                <Button
 onClick={handleEdit}
 variant="primary"
 data-testid="btn-link-to-asset">
                  Link to Asset
                </Button>
              )}
              <Button onClick={handleDeleteClick} variant="danger" loading={deleteMutation.isPending}>
                Delete
              </Button>
            </>
          ) : (
            <>
              <Button onClick={() => setIsEditing(false)} variant="secondary">Cancel</Button>
              <Button onClick={handleSave} variant="primary" loading={updateMutation.isPending}>
                Save
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="dataset-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Datasets', href: '/datasets' },
            { label: dataset.name || 'Dataset' },
          ]}
        />
        {isEditing ? (
          <div className="dataset-edit-form" data-testid="dataset-edit-form">
            <div className="form-group form-group-readonly">
              <label>Name</label>
              <p className="form-readonly-value" aria-readonly="true">
                {dataset.name || '—'} <span className="form-hint">(derived from file, read-only)</span>
              </p>
            </div>
            <div className="form-group">
              <label>Asset (optional)</label>
              <AssetPicker
                value={editData.asset_id}
                onChange={(assetId) => setEditData((prev) => ({ ...prev, asset_id: assetId }))}
                placeholder="Search and select an asset to link (clear to unlink)"
                data-testid="dataset-asset-picker"
              />
            </div>
          </div>
        ) : (
          <>
            <h1>{dataset.name || 'Dataset'}</h1>
            {id && (
              <div className="dataset-uuid" data-testid="dataset-uuid">
                <UuidWithCopy value={id} label="Dataset ID" />
              </div>
            )}
            {dataset.description && <p className="dataset-description">{dataset.description}</p>}
            {(dataset.asset_id || dataset.asset) && (
              <p className="dataset-linked-asset" data-testid="dataset-linked-asset">
                Linked asset:{' '}
                <Link
                  to={`/assets/${dataset.asset_id || dataset.asset}`}
                  data-testid="dataset-asset-link"
                >
                  {dataset.asset_name || 'View asset'}
                </Link>
              </p>
            )}

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

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
        title="Delete dataset"
        message="Are you sure you want to delete this dataset? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
