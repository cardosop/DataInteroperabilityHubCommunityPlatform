/**
 * Dataset Create Page
 * Create dataset from uploaded file
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateDataset } from '../hooks/useDatasets';
import { FileUpload } from '../../files/components/FileUpload';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import type { File } from '../../../shared/types/files';
import './DatasetCreatePage.css';

export function DatasetCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateDataset();
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [assetId, setAssetId] = useState('');

  const handleFileUploaded = (file: File) => {
    setUploadedFile(file);
  };

  const handleCreate = async () => {
    if (!uploadedFile) return;

    try {
      const dataset = await createMutation.mutateAsync({
        file_id: uploadedFile.id,
        asset_id: assetId.trim() || undefined,
      });
      navigate(`/datasets/${dataset.id}`);
    } catch (error) {
      // Error handled by mutation
    }
  };

  return (
    <div className="dataset-create-page">
      <div className="dataset-create-header">
        <button onClick={() => navigate('/datasets')} className="btn-back" type="button">
          ← Back to Datasets
        </button>
        <h1>Create Dataset</h1>
      </div>

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create dataset"
          onRetry={() => createMutation.reset()}
        />
      )}

      <div className="dataset-create-content">
        <div className="form-section">
          <h2>Upload File</h2>
          <FileUpload
            onUploadComplete={handleFileUploaded}
            accept=".csv,.json,.parquet"
          />
          {uploadedFile && (
            <div className="upload-success">
              ✓ File uploaded: {uploadedFile.name} ({(uploadedFile.size / 1024).toFixed(2)} KB)
            </div>
          )}
        </div>

        <div className="form-section">
          <h2>Link to Asset (Optional)</h2>
          <input
            type="text"
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
            placeholder="Asset ID (optional)"
            className="asset-id-input"
          />
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={() => navigate('/datasets')}
            className="btn-secondary"
            disabled={createMutation.isPending}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            className="btn-primary"
            disabled={!uploadedFile || createMutation.isPending}
            type="button"
          >
            {createMutation.isPending ? (
              <>
                <LoadingSpinner size="small" />
                Creating Dataset...
              </>
            ) : (
              'Create Dataset'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
