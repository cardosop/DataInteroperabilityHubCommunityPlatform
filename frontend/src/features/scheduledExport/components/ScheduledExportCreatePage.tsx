/**
 * Scheduled Export Create Page
 * Form to create a new scheduled export.
 * Uses AssetMultiPicker, DatasetMultiPicker, FileMultiPicker for source scope;
 * ContractPicker for contract_id (task 29.69.6.1).
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AssetMultiPicker,
  ContractPicker,
  DatasetMultiPicker,
  FileMultiPicker,
} from '../../../shared/components/pickers';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { DestinationType } from '../../../shared/types/scheduledExport';
import { useCreateScheduledExport } from '../hooks/useScheduledExport';
import './ScheduledExportCreatePage.css';
import { Button } from '../../../shared/components/Button';

export function ScheduledExportCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateScheduledExport();
  const [name, setName] = useState('');
  const [destinationType, setDestinationType] = useState<DestinationType>('S3');
  const [cronExpression, setCronExpression] = useState('0 2 * * *'); // Daily at 2 AM
  const [timezone, setTimezone] = useState('UTC');
  const [assetIds, setAssetIds] = useState<string[]>([]);
  const [datasetIds, setDatasetIds] = useState<string[]>([]);
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [contractId, setContractId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const sourceScope: {
        asset_ids?: string[];
        dataset_ids?: string[];
        file_ids?: string[];
        contract_id?: string;
      } = {};
      if (assetIds.length > 0) sourceScope.asset_ids = assetIds;
      if (datasetIds.length > 0) sourceScope.dataset_ids = datasetIds;
      if (fileIds.length > 0) sourceScope.file_ids = fileIds;
      if (contractId) sourceScope.contract_id = contractId;

      // Build destination config (minimal valid config)
      let destinationConfig: Record<string, unknown> = {};
      if (destinationType === 'S3') {
        destinationConfig = { bucket: 'placeholder-bucket' }; // Will need proper form later
      } else if (destinationType === 'GCS') {
        destinationConfig = { bucket: 'placeholder-bucket' };
      } else if (destinationType === 'AZURE_BLOB') {
        destinationConfig = { account_name: 'placeholder', container: 'placeholder' };
      }

      // Backend validation requires at least one scope field with a non-empty value
      // Empty arrays [] are falsy and will fail backend validation
      // Let backend handle validation and show error via ErrorDisplay

      const export_ = await createMutation.mutateAsync({
        name,
        schedule_config: {
          cron: cronExpression,
          timezone: timezone || undefined,
        },
        destination_type: destinationType,
        destination_config: destinationConfig,
        source_scope: sourceScope,
      });
      navigate(`/scheduled-exports/${export_.id}`);
    } catch (err) {
      // Error handled by mutation
      console.error('Create failed:', err);
    }
  };

  return (
    <div className="scheduled-export-create-page" data-testid="scheduled-export-create-page">
      <div className="scheduled-export-create-header">
        <Button
 variant="secondary"
 onClick={() => navigate('/scheduled-exports')}>
          ← Back to Scheduled Exports
        </Button>
        <h1>Create Scheduled Export</h1>
      </div>

      {!!createMutation.error && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create scheduled export"
          onRetry={() => createMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="scheduled-export-create-form">
        <div className="form-group">
          <label htmlFor="name">
            Name <span className="required">*</span>
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g., Daily Sales Data Export"
          />
        </div>

        <div className="form-group">
          <label htmlFor="destination_type">
            Destination Type <span className="required">*</span>
          </label>
          <select
            id="destination_type"
            value={destinationType}
            onChange={(e) => setDestinationType(e.target.value as DestinationType)}
            required
          >
            <option value="S3">Amazon S3</option>
            <option value="GCS">Google Cloud Storage</option>
            <option value="AZURE_BLOB">Azure Blob Storage</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="cron">
            Cron Expression <span className="required">*</span>
          </label>
          <input
            id="cron"
            name="cron"
            type="text"
            value={cronExpression}
            onChange={(e) => setCronExpression(e.target.value)}
            required
            placeholder="0 2 * * *"
            title="Cron expression (e.g., 0 2 * * * for daily at 2 AM)"
          />
          <small>Example: 0 2 * * * (daily at 2 AM)</small>
        </div>

        <div className="form-group">
          <label htmlFor="timezone">Timezone</label>
          <input
            id="timezone"
            type="text"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            placeholder="UTC"
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset_ids">Assets</label>
          <AssetMultiPicker
            value={assetIds}
            onChange={setAssetIds}
            placeholder="Search and select assets..."
            data-testid="scheduled-export-asset-picker"
          />
        </div>

        <div className="form-group">
          <label htmlFor="dataset_ids">Datasets</label>
          <DatasetMultiPicker
            value={datasetIds}
            onChange={setDatasetIds}
            placeholder="Search and select datasets..."
            data-testid="scheduled-export-dataset-picker"
          />
        </div>

        <div className="form-group">
          <label htmlFor="file_ids">Files</label>
          <FileMultiPicker
            value={fileIds}
            onChange={setFileIds}
            placeholder="Search and select files..."
            data-testid="scheduled-export-file-picker"
          />
        </div>

        <div className="form-group">
          <label htmlFor="contract_id">Contract</label>
          <ContractPicker
            value={contractId}
            onChange={setContractId}
            placeholder="Search and select a contract..."
            data-testid="scheduled-export-contract-picker"
          />
        </div>

        <div className="form-actions">
          <Button
 variant="secondary"
 onClick={() => navigate('/scheduled-exports')}>
            Cancel
          </Button>
          <Button
 type="submit"
 variant="primary"
 disabled={createMutation.isPending || !name || !cronExpression}>
            {createMutation.isPending ? 'Creating...' : 'Create'}
          </Button>
        </div>
      </form>

      {createMutation.isPending && <LoadingSpinner message="Creating scheduled export..." />}
    </div>
  );
}
