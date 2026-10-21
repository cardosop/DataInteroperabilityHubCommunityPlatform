/**
 * Dataset Create Page
 * Create dataset from uploaded file with flow selector:
 * - none: Create dataset only (no asset linking)
 * - existing: Select existing asset via AssetPicker
 * - create_new: Create new asset and link via data-first API
 */

import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useCreateDataset } from '../hooks/useDatasets';
import { useDataFirstAsset } from '../../assets/hooks/useAssets';
import { FileUpload } from '../../files/components/FileUpload';
import { AssetPicker } from '../../../shared/components/pickers';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import type { File } from '../../../shared/types/files';
import './DatasetCreatePage.css';
import { Button } from '../../../shared/components/Button';

export type LinkMode = 'none' | 'existing' | 'create_new';

function slugify(name: string): string {
  return name
    .replace(/\.[^/.]+$/, '')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase() || 'dataset';
}

export function DatasetCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const createMutation = useCreateDataset();
  const dataFirstMutation = useDataFirstAsset();

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const linkModeParam = searchParams.get('linkMode');
  const initialLinkMode: LinkMode =
    linkModeParam === 'create_new' || linkModeParam === 'existing' || linkModeParam === 'none'
      ? linkModeParam
      : 'none';
  const [linkMode, setLinkMode] = useState<LinkMode>(initialLinkMode);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [createNewKey, setCreateNewKey] = useState('');
  const [createNewName, setCreateNewName] = useState('');

  useEffect(() => {
    if (linkModeParam === 'create_new' || linkModeParam === 'existing' || linkModeParam === 'none') {
      setLinkMode(linkModeParam);
    }
  }, [linkModeParam]);

  useEffect(() => {
    if (uploadedFile && linkMode === 'create_new') {
      const base = slugify(uploadedFile.name);
      setCreateNewKey(base || 'dataset');
      setCreateNewName(uploadedFile.name.replace(/\.[^/.]+$/, '') || 'Dataset');
    }
  }, [uploadedFile, linkMode]);

  const handleFileUploaded = (file: File) => {
    setUploadedFile(file);
  };

  const isPending = createMutation.isPending || dataFirstMutation.isPending;
  const mutationError = createMutation.error ?? dataFirstMutation.error;

  const handleSubmit = async () => {
    if (!uploadedFile) return;

    if (linkMode === 'create_new') {
      const key = createNewKey.trim() || slugify(uploadedFile.name) || 'dataset';
      const name = createNewName.trim() || uploadedFile.name.replace(/\.[^/.]+$/, '') || 'Dataset';
      if (!key || !name) {
        toast.error('Asset key and name are required for create-new flow.');
        return;
      }
      try {
        const result = await dataFirstMutation.mutateAsync({
          file_id: uploadedFile.id,
          key,
          name,
        });
        toast.success('Asset and dataset created successfully.');
        navigate(`/assets/${result.asset_id}`);
      } catch (error) {
        toast.error(normalizeError(error).error.message || 'Failed to create asset and dataset');
      }
      return;
    }

    if (linkMode === 'existing') {
      if (!selectedAssetId) {
        toast.error('Please select an asset to link.');
        return;
      }
      try {
        const dataset = await createMutation.mutateAsync({
          file_id: uploadedFile.id,
          asset_id: selectedAssetId,
        });
        toast.success('Dataset created and linked to asset.');
        navigate(`/datasets/${dataset.id}`);
      } catch (error) {
        toast.error(normalizeError(error).error.message || 'Failed to create dataset');
      }
      return;
    }

    try {
      const dataset = await createMutation.mutateAsync({
        file_id: uploadedFile.id,
      });
      toast.success('Dataset created successfully.');
      navigate(`/datasets/${dataset.id}`);
    } catch (error) {
      toast.error(normalizeError(error).error.message || 'Failed to create dataset');
    }
  };

  const canSubmit =
    uploadedFile &&
    (linkMode !== 'existing' || selectedAssetId) &&
    (linkMode !== 'create_new' || (createNewKey.trim() && createNewName.trim()));

  return (
    <div className="dataset-create-page" data-testid="dataset-create-page">
      <div className="dataset-create-header">
        <Button onClick={() => navigate('/datasets')} variant="ghost">
          ← Back to Datasets
        </Button>
        <h1>Create Dataset</h1>
      </div>

      {!!mutationError && (
        <ErrorDisplay
          error={mutationError}
          title="Failed to create dataset"
          onRetry={() => {
            createMutation.reset();
            dataFirstMutation.reset();
          }}
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
          <h2>Link to Asset</h2>
          <fieldset className="flow-selector" role="group" aria-label="Asset linking mode">
            <legend className="flow-selector-legend">Choose how to link this dataset</legend>
            <label className="flow-option">
              <input
                type="radio"
                name="linkMode"
                value="none"
                checked={linkMode === 'none'}
                onChange={() => setLinkMode('none')}
                data-testid="flow-none"
              />
              <span>Create dataset only (no asset linking)</span>
            </label>
            <label className="flow-option">
              <input
                type="radio"
                name="linkMode"
                value="existing"
                checked={linkMode === 'existing'}
                onChange={() => setLinkMode('existing')}
                data-testid="flow-existing"
              />
              <span>Link to existing asset</span>
            </label>
            <label className="flow-option">
              <input
                type="radio"
                name="linkMode"
                value="create_new"
                checked={linkMode === 'create_new'}
                onChange={() => setLinkMode('create_new')}
                data-testid="flow-create-new"
              />
              <span>Create new asset and link</span>
            </label>
          </fieldset>

          {linkMode === 'existing' && (
            <div className="form-section asset-picker-section">
              <AssetPicker
                value={selectedAssetId}
                onChange={setSelectedAssetId}
                placeholder="Search and select an asset..."
                data-testid="asset-picker"
              />
            </div>
          )}

          {linkMode === 'create_new' && (
            <div className="form-section create-new-fields">
              <label htmlFor="create-new-key">
                Asset key <span className="required">*</span>
              </label>
              <input
                id="create-new-key"
                type="text"
                value={createNewKey}
                onChange={(e) => setCreateNewKey(e.target.value)}
                placeholder="e.g. my-dataset"
                className="asset-id-input"
                data-testid="create-new-key"
              />
              <label htmlFor="create-new-name">
                Asset name <span className="required">*</span>
              </label>
              <input
                id="create-new-name"
                type="text"
                value={createNewName}
                onChange={(e) => setCreateNewName(e.target.value)}
                placeholder="e.g. My Dataset"
                className="asset-id-input"
                data-testid="create-new-name"
              />
              <p className="form-hint">
                A new asset, contract, and dataset will be created from the uploaded file.
              </p>
            </div>
          )}
        </div>

        <div className="form-actions">
          <Button
 onClick={() => navigate('/datasets')}
 variant="secondary"
 disabled={isPending}>
            Cancel
          </Button>
          <Button
 onClick={handleSubmit}
 variant="primary"
 disabled={!canSubmit || isPending}
 data-testid="btn-create-dataset">
            {isPending ? (
              <>
                <LoadingSpinner size="small" />
                {linkMode === 'create_new' ? 'Creating Asset & Dataset...' : 'Creating Dataset...'}
              </>
            ) : (
              linkMode === 'create_new' ? 'Create Asset & Dataset' : 'Create Dataset'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
