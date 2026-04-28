/**
 * AssetCreatePage — unified adaptive form for creating assets.
 *
 * Always-visible: Name (auto-populates Key), Key, Domain, Visibility.
 * Collapsible: "+ Add data file" (FileUpload), "+ Add contract" (ContractFileReader).
 *
 * Submit orchestration branches on what the user provided:
 * - metadata only → POST /assets/
 * - data only → POST /assets/data-first/
 * - contract only → POST /assets/ + contract pipeline
 * - data + contract → POST /assets/ + POST /datasets/ + contract pipeline
 */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateAsset, useDataFirstAsset } from '../hooks/useAssets';
import { useCreateContract, useCreateODPSProduct } from '../../contracts/hooks/useContracts';
import { useCreateDataset } from '../../datasets/hooks/useDatasets';
import { ContractFileReader } from '../../../shared/components/ContractFileReader';
import { FileUpload } from '../../files/components/FileUpload';
import { CreateAssetSummary } from './CreateAssetSummary';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import type { DetectedSpec } from '../../../shared/utils/detectSpecType';
import type { AssetVisibility } from '../../../shared/types/assets';
import type { File as AppFile } from '../../../shared/types/files';
import './AssetCreatePage.css';

const BREADCRUMBS = [
  { label: 'Home', href: '/' },
  { label: 'Assets', href: '/assets' },
  { label: 'Create' },
];

function slugify(name: string): string {
  return name
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase() || '';
}

export function AssetCreatePage() {
  const navigate = useNavigate();
  const toast = useToast();

  // Metadata
  const [name, setName] = useState('');
  const [key, setKey] = useState('');
  const [keyEdited, setKeyEdited] = useState(false);
  const [description, setDescription] = useState('');
  const [domain, setDomain] = useState('');
  const [visibility, setVisibility] = useState<AssetVisibility>('INTERNAL');

  // Collapsible sections
  const [showDataFile, setShowDataFile] = useState(false);
  const [showContract, setShowContract] = useState(false);

  // Data file state
  const [uploadedFile, setUploadedFile] = useState<AppFile | null>(null);

  // Contract state
  const [contractContent, setContractContent] = useState('');
  const [contractFormat, setContractFormat] = useState('yaml');
  const [detected, setDetected] = useState<DetectedSpec | null>(null);

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [currentStep, setCurrentStep] = useState('');
  const [error, setError] = useState<Error | null>(null);

  // Mutations
  const createAsset = useCreateAsset();
  const dataFirstAsset = useDataFirstAsset();
  const createContract = useCreateContract();
  const createODPS = useCreateODPSProduct();
  const createDataset = useCreateDataset();

  const hasDataFile = !!uploadedFile;
  const hasContract = contractContent.trim().length > 0;
  const isODPS = detected?.type === 'ODPS';

  // Auto-populate key from name (unless user edited key manually)
  const handleNameChange = useCallback((value: string) => {
    setName(value);
    if (!keyEdited) {
      setKey(slugify(value));
    }
  }, [keyEdited]);

  const handleKeyChange = useCallback((value: string) => {
    setKey(value);
    setKeyEdited(true);
  }, []);

  const handleContentChange = useCallback((content: string, format: string) => {
    setContractContent(content);
    setContractFormat(format);
  }, []);

  const handleDetection = useCallback((result: DetectedSpec) => {
    setDetected(result);
  }, []);

  const handleFileUploadComplete = useCallback((file: AppFile) => {
    setUploadedFile(file);
    // Auto-fill name from filename if empty
    if (!name) {
      const fileName = file.name.replace(/\.[^/.]+$/, '');
      handleNameChange(fileName);
    }
  }, [name, handleNameChange]);

  const handleSubmit = async () => {
    if (!name.trim() || !key.trim()) {
      toast.error('Name and Key are required');
      return;
    }

    setSubmitting(true);
    setError(null);
    let assetId: string | undefined;

    try {
      if (hasDataFile && !hasContract) {
        // Data-first: single API call
        setCurrentStep('Creating asset with dataset...');
        const result = await dataFirstAsset.mutateAsync({
          file_id: uploadedFile!.id,
          key: key.trim(),
          name: name.trim(),
          description: description.trim() || undefined,
          domain: domain.trim() || undefined,
        });
        assetId = result.asset_id;
      } else {
        // Step 1: Create asset
        setCurrentStep('Creating asset...');
        const asset = await createAsset.mutateAsync({
          key: key.trim(),
          name: name.trim(),
          description: description.trim() || undefined,
          domain: domain.trim() || undefined,
          visibility,
        });
        assetId = asset.id;

        // Step 2: Create dataset if file was uploaded (data + contract case)
        if (hasDataFile && uploadedFile) {
          setCurrentStep('Creating dataset...');
          try {
            await createDataset.mutateAsync({
              file_id: uploadedFile.id,
              asset_id: assetId,
            });
          } catch (datasetErr) {
            toast.error(`Asset created but dataset failed: ${(datasetErr as Error).message}`);
          }
        }

        // Step 3: Create contract if provided
        if (hasContract) {
          setCurrentStep('Processing contract...');
          const format = contractFormat === 'json' ? 'JSON' : 'YAML';
          try {
            if (isODPS) {
              await createODPS.mutateAsync({
                original_raw: contractContent,
                original_format: format,
                asset_id: assetId,
              });
            } else {
              await createContract.mutateAsync({
                original_raw: contractContent,
                original_format: format,
                original_spec_type: detected?.type,
                asset_id: assetId,
              });
            }
          } catch (contractErr) {
            toast.error(`Asset created but contract failed: ${(contractErr as Error).message}`);
          }
        }
      }

      if (assetId) {
        navigate(`/assets/${assetId}`);
      }
    } catch (err) {
      setError(err as Error);
    } finally {
      setSubmitting(false);
      setCurrentStep('');
    }
  };

  return (
    // Phase 226.F1.b — testid for stable e2e selector.
    <div className="asset-create-page" data-testid="asset-create-page">
      <div className="asset-create-header">
        <Breadcrumbs items={BREADCRUMBS} />
        <h1>Create Asset</h1>
      </div>

      <div className="asset-create-form" data-testid="asset-create-form">
        {/* Always-visible metadata */}
        <div className="form-group">
          <label htmlFor="asset-name">Name <span className="required">*</span></label>
          <input
            id="asset-name"
            data-testid="asset-create-name"
            type="text"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="My Asset"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-key">Key <span className="required">*</span></label>
          <input
            id="asset-key"
            data-testid="asset-create-key"
            type="text"
            value={key}
            onChange={(e) => handleKeyChange(e.target.value)}
            placeholder="my-asset-key"
            required
          />
          <p className="field-hint">Unique identifier (auto-generated from name)</p>
        </div>

        <div className="form-group">
          <label htmlFor="asset-description">Description</label>
          <textarea
            id="asset-description"
            data-testid="asset-create-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Brief description of this asset..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-domain">Domain</label>
          <input
            id="asset-domain"
            data-testid="asset-create-domain"
            type="text"
            list="domain-suggestions"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="marketing, sales, etc."
          />
          <datalist id="domain-suggestions">
            <option value="marketing" />
            <option value="sales" />
            <option value="finance" />
            <option value="engineering" />
            <option value="analytics" />
            <option value="operations" />
            <option value="product" />
            <option value="customer-success" />
          </datalist>
          <p className="field-hint">Select or type a domain</p>
        </div>

        <div className="form-group">
          <label htmlFor="asset-visibility">Visibility</label>
          <select
            id="asset-visibility"
            data-testid="asset-create-visibility"
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as AssetVisibility)}
          >
            <option value="INTERNAL">Internal</option>
            <option value="EXTERNAL">External</option>
            <option value="PUBLIC">Public</option>
          </select>
        </div>

        {/* Collapsible: Add data file */}
        <div className="asset-create-section">
          <button
            type="button"
            className="asset-create-section__toggle"
            aria-expanded={showDataFile}
            aria-controls="data-file-section"
            onClick={() => setShowDataFile(!showDataFile)}
          >
            {showDataFile ? '− Remove data file' : '+ Add data file'}
          </button>
          {showDataFile && (
            <div id="data-file-section" className="asset-create-section__content">
              <FileUpload
                onUploadComplete={handleFileUploadComplete}
                accept=".csv,.json,.parquet,.xlsx"
              />
              {uploadedFile && (
                <p className="asset-create-section__file-name">
                  Uploaded: {uploadedFile.name}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Collapsible: Add contract */}
        <div className="asset-create-section">
          <button
            type="button"
            className="asset-create-section__toggle"
            aria-expanded={showContract}
            aria-controls="contract-section"
            onClick={() => setShowContract(!showContract)}
          >
            {showContract ? '− Remove contract' : '+ Add contract'}
          </button>
          {showContract && (
            <div id="contract-section" className="asset-create-section__content">
              <ContractFileReader
                onContentChange={handleContentChange}
                onDetection={handleDetection}
              />
            </div>
          )}
        </div>

        {/* Summary */}
        <CreateAssetSummary
          hasDataFile={hasDataFile}
          hasContract={hasContract}
          detectedSpecType={detected?.type !== 'UNKNOWN' ? detected?.type : undefined}
          submitting={submitting}
          currentStep={currentStep}
        />

        {error && (
          <ErrorDisplay
            error={error}
            title="Failed to create asset"
            onRetry={() => setError(null)}
          />
        )}

        {/* Actions */}
        <div className="form-actions">
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!name.trim() || !key.trim() || submitting}
            data-testid="asset-create-submit"
          >
            {submitting ? 'Creating...' : 'Create Asset'}
          </Button>
        </div>
      </div>
    </div>
  );
}
