/**
 * Scheduled Export Edit Page
 * Form to edit an existing scheduled export
 */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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
  const [assetIds, setAssetIds] = useState('');
  const [datasetIds, setDatasetIds] = useState('');
  const [fileIds, setFileIds] = useState('');
  const [contractId, setContractId] = useState('');

  useEffect(() => {
    if (export_) {
      setName(export_.name);
      setDestinationType(export_.destination_type);
      setCronExpression(export_.schedule_config.cron);
      setTimezone(export_.schedule_config.timezone || '');
      setAssetIds(export_.source_scope.asset_ids?.join(', ') || '');
      setDatasetIds(export_.source_scope.dataset_ids?.join(', ') || '');
      setFileIds(export_.source_scope.file_ids?.join(', ') || '');
      setContractId(export_.source_scope.contract_id || '');
    }
  }, [export_]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      // Build source scope
      const sourceScope: {
        asset_ids?: string[];
        dataset_ids?: string[];
        file_ids?: string[];
        contract_id?: string;
      } = {};
      if (assetIds.trim()) {
        sourceScope.asset_ids = assetIds
          .split(',')
          .map((id) => id.trim())
          .filter(Boolean);
      }
      if (datasetIds.trim()) {
        sourceScope.dataset_ids = datasetIds
          .split(',')
          .map((id) => id.trim())
          .filter(Boolean);
      }
      if (fileIds.trim()) {
        sourceScope.file_ids = fileIds
          .split(',')
          .map((id) => id.trim())
          .filter(Boolean);
      }
      if (contractId.trim()) {
        sourceScope.contract_id = contractId.trim();
      }

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
          onRetry={() => {}}
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
          <label htmlFor="asset_ids">Asset IDs (comma-separated)</label>
          <input
            id="asset_ids"
            type="text"
            value={assetIds}
            onChange={(e) => setAssetIds(e.target.value)}
            placeholder="uuid1, uuid2, ..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="dataset_ids">Dataset IDs (comma-separated)</label>
          <input
            id="dataset_ids"
            type="text"
            value={datasetIds}
            onChange={(e) => setDatasetIds(e.target.value)}
            placeholder="uuid1, uuid2, ..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="file_ids">File IDs (comma-separated)</label>
          <input
            id="file_ids"
            type="text"
            value={fileIds}
            onChange={(e) => setFileIds(e.target.value)}
            placeholder="uuid1, uuid2, ..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="contract_id">Contract ID</label>
          <input
            id="contract_id"
            type="text"
            value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            placeholder="uuid"
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
