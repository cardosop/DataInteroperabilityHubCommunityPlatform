/**
 * Scheduled Ingestion Edit Page
 * Form to edit an existing scheduled ingestion
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useScheduledIngestion,
  useUpdateScheduledIngestion,
} from '../hooks/useScheduledIngestion';
import type { SourceType, ScheduleType } from '../../../shared/types/scheduledIngestion';
import './ScheduledIngestionEditPage.css';
import { Button } from '../../../shared/components/Button';

export function ScheduledIngestionEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: schedule, isLoading, error, refetch } = useScheduledIngestion(id || null);
  const updateMutation = useUpdateScheduledIngestion();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('S3');
  const [scheduleType, setScheduleType] = useState<ScheduleType>('DAILY');

  useEffect(() => {
    if (schedule) {
      setName(schedule.name);
      setDescription(schedule.description || '');
      setSourceType(schedule.source_type);
      setScheduleType(schedule.schedule_type);
    }
  }, [schedule]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      await updateMutation.mutateAsync({
        id,
        data: {
          name,
          description: description || undefined,
          source_type: sourceType,
          schedule_type: scheduleType,
        },
      });
      navigate(`/scheduled-ingestions/${id}`);
    } catch (err) {
      console.error('Update failed:', err);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading scheduled ingestion..." />;
  }

  if (error || !schedule) {
    return (
      <ErrorDisplay
        error={error || new Error('Scheduled ingestion not found')}
        title="Failed to load scheduled ingestion"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="scheduled-ingestion-edit-page" data-testid="scheduled-ingestion-edit-page">
      <div className="scheduled-ingestion-edit-header">
        <Button
 variant="secondary"
 onClick={() => navigate(`/scheduled-ingestions/${id}`)}>
          ← Back to Detail
        </Button>
        <h1>Edit Scheduled Ingestion</h1>
      </div>

      {!!updateMutation.error && (
        <ErrorDisplay
          error={updateMutation.error}
          title="Failed to update scheduled ingestion"
          onRetry={() => {}}
        />
      )}

      <form onSubmit={handleSubmit} className="scheduled-ingestion-edit-form">
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
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
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
 onClick={() => navigate(`/scheduled-ingestions/${id}`)}>
            Cancel
          </Button>
          <Button
 type="submit"
 variant="primary"
 disabled={updateMutation.isPending || !name}>
            {updateMutation.isPending ? 'Updating...' : 'Update'}
          </Button>
        </div>
      </form>

      {updateMutation.isPending && <LoadingSpinner message="Updating scheduled ingestion..." />}
    </div>
  );
}
