/**
 * Scheduled Ingestion Create Page
 * Form to create a new scheduled ingestion
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useCreateScheduledIngestion } from '../hooks/useScheduledIngestion';
import type { SourceType, ScheduleType } from '../../../shared/types/scheduledIngestion';
import './ScheduledIngestionCreatePage.css';
import { Button } from '../../../shared/components/Button';

export function ScheduledIngestionCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateScheduledIngestion();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('S3');
  const [scheduleType, setScheduleType] = useState<ScheduleType>('DAILY');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Provide minimal valid configs based on source_type and schedule_type
      let sourceConfig: Record<string, unknown> = {};
      if (sourceType === 'S3' || sourceType === 'GCS') {
        sourceConfig = { bucket: 'placeholder-bucket' }; // Will need proper form later
      } else if (sourceType === 'AZURE_BLOB') {
        sourceConfig = { account_name: 'placeholder', container: 'placeholder' };
      } else if (sourceType === 'HTTP' || sourceType === 'HTTPS') {
        sourceConfig = { base_url: 'https://example.com' };
      } else if (sourceType === 'FTP' || sourceType === 'SFTP') {
        sourceConfig = { host: 'example.com' };
      } else if (sourceType === 'DATABASE') {
        sourceConfig = { host: 'localhost', database: 'placeholder' };
      }

      let scheduleConfig: Record<string, unknown> = {};
      if (scheduleType === 'CUSTOM_CRON') {
        scheduleConfig = { cron: '0 2 * * *' }; // Daily at 2 AM
      } else {
        scheduleConfig = { time: '02:00' }; // Default time for DAILY/WEEKLY/MONTHLY
      }

      const schedule = await createMutation.mutateAsync({
        name,
        description: description || undefined,
        source_type: sourceType,
        source_config: sourceConfig,
        schedule_type: scheduleType,
        schedule_config: scheduleConfig,
        file_pattern: '.*', // Default: match all files (can be customized later)
        test_connection: false, // Skip connection test for now (requires valid credentials)
      });
      navigate(`/scheduled-ingestions/${schedule.id}`);
    } catch (err) {
      // Error handled by mutation
      console.error('Create failed:', err);
    }
  };

  return (
    <div className="scheduled-ingestion-create-page" data-testid="scheduled-ingestion-create-page">
      <div className="scheduled-ingestion-create-header">
        <Button
 variant="secondary"
 onClick={() => navigate('/scheduled-ingestions')}>
          ← Back to Scheduled Ingestion
        </Button>
        <h1>Create Scheduled Ingestion</h1>
      </div>

      {!!createMutation.error && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create scheduled ingestion"
          onRetry={() => {}}
        />
      )}

      <form onSubmit={handleSubmit} className="scheduled-ingestion-create-form">
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
            placeholder="e.g., Daily Sales Data Ingestion"
          />
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Optional description"
          />
        </div>

        <div className="form-group">
          <label htmlFor="source_type">
            Source Type <span className="required">*</span>
          </label>
          <select
            id="source_type"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as SourceType)}
            required
          >
            <option value="S3">Amazon S3</option>
            <option value="GCS">Google Cloud Storage</option>
            <option value="AZURE_BLOB">Azure Blob Storage</option>
            <option value="HTTP">HTTP</option>
            <option value="HTTPS">HTTPS</option>
            <option value="FTP">FTP</option>
            <option value="SFTP">SFTP</option>
            <option value="DATABASE">Database</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="schedule_type">
            Schedule Type <span className="required">*</span>
          </label>
          <select
            id="schedule_type"
            value={scheduleType}
            onChange={(e) => setScheduleType(e.target.value as ScheduleType)}
            required
          >
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="CUSTOM_CRON">Custom Cron</option>
          </select>
        </div>

        <div className="form-actions">
          <Button
 variant="secondary"
 onClick={() => navigate('/scheduled-ingestions')}>
            Cancel
          </Button>
          <Button
 type="submit"
 variant="primary"
 disabled={createMutation.isPending || !name}>
            {createMutation.isPending ? 'Creating...' : 'Create'}
          </Button>
        </div>
      </form>

      {createMutation.isPending && <LoadingSpinner message="Creating scheduled ingestion..." />}
    </div>
  );
}
