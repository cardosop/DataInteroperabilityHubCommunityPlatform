/**
 * Scheduled Export Edit Page
 * Form to edit an existing scheduled export.
 * Uses AssetMultiPicker, DatasetMultiPicker, FileMultiPicker for source scope;
 * ContractPicker for contract_id (task 29.69.6.1).
 */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  AssetMultiPicker,
  ContractPicker,
  DatasetMultiPicker,
  FileMultiPicker,
} from '../../../shared/components/pickers';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { DestinationType } from '../../../shared/types/scheduledExport';
import { useScheduledExport, useUpdateScheduledExport } from '../hooks/useScheduledExport';
import './ScheduledExportEditPage.css';

export function ScheduledExportEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: export_, isLoading, error, refetch } = useScheduledExport(id || null);
  const updateMutation = useUpdateScheduledExport();
  const [name, setName] = useState('');
  const [destinationType, setDestinationType] = useState<DestinationType>('S3');
  const [cronExpression, setCronExpression] = useState('');
  const [timezone, setTimezone] = useState('');
  const [assetIds, setAssetIds] = useState<string[]>([]);
  const [datasetIds, setDatasetIds] = useState<string[]>([]);
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [contractId, setContractId] = useState<string | null>(null);

  useEffect(() => {
    if (export_) {
      setName(export_.name);
      setDestinationType(export_.destination_type);
      setCronExpression(export_.schedule_config.cron);
      setTimezone(export_.schedule_config.timezone || '');
      setAssetIds(export_.source_scope.asset_ids ?? []);
      setDatasetIds(export_.source_scope.dataset_ids ?? []);
      setFileIds(export_.source_scope.file_ids ?? []);
      setContractId(export_.source_scope.contract_id ?? null);
    }
  }, [export_]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
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

      await updateMutation.mutateAsync({
        id,
        data: {
          name,
          destination_type: destinationType,
          schedule_config: {
            cron: cronExpression,
            timezone: timezone || undefined,
          },
          source_scope: sourceScope,
        },
      });
      navigate(`/scheduled-exports/${id}`);
    } catch (err) {
      console.error('Update failed:', err);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading scheduled export..." />;
  }

  if (error || !export_) {
    return (
      <ErrorDisplay
        error={error || new Error('Scheduled export not found')}
        title="Failed to load scheduled export"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="scheduled-export-edit-page" data-testid="scheduled-export-edit-page">
      <div className="scheduled-export-edit-header">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => navigate(`/scheduled-exports/${id}`)}
        >
          ← Back to Detail
        </button>
        <h1>Edit Scheduled Export</h1>
      </div>

      {updateMutation.error && (
        <ErrorDisplay
          error={updateMutation.error}
          title="Failed to update scheduled export"
          onRetry={() => updateMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="scheduled-export-edit-form">
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
            type="text"
            value={cronExpression}
            onChange={(e) => setCronExpression(e.target.value)}
            required
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
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate(`/scheduled-exports/${id}`)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={updateMutation.isPending || !name || !cronExpression}
          >
            {updateMutation.isPending ? 'Updating...' : 'Update'}
          </button>
        </div>
      </form>

      {updateMutation.isPending && <LoadingSpinner message="Updating scheduled export..." />}
    </div>
  );
}
