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
import { DatabricksWarehousePicker } from '../../warehouses/components/DatabricksWarehousePicker';

export function ScheduledIngestionCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateScheduledIngestion();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('S3');
  const [scheduleType, setScheduleType] = useState<ScheduleType>('DAILY');
  const [credentialRef, setCredentialRef] = useState('');
  // 6.8 (design D8) — the DATABRICKS_SOURCE picker state: the stored
  // http_path is DERIVED from the picked warehouse, never hand-typed.
  const [databricksHost, setDatabricksHost] = useState<string | undefined>();
  const [databricksHttpPath, setDatabricksHttpPath] = useState<string | undefined>();
  const [catalog, setCatalog] = useState('main');
  const [schema, setSchema] = useState('default');
  const [formError, setFormError] = useState<string | null>(null);
  // Real S3 source fields — the placeholder ``{bucket: 'placeholder-bucket'}``
  // could never run (a UI-created ingestion had no reachable source), which
  // is what the JOURNEY-INGESTION-001 E2E needs the app to actually do.
  const [s3Bucket, setS3Bucket] = useState('');
  const [s3Prefix, setS3Prefix] = useState('');
  const [s3Endpoint, setS3Endpoint] = useState('');
  const [s3AccessKeyId, setS3AccessKeyId] = useState('');
  const [s3SecretAccessKey, setS3SecretAccessKey] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    // 6.8 — the derived path is the ONLY Databricks http_path: refuse the
    // submit until a warehouse is picked (fail-closed, never a placeholder).
    if (sourceType === 'DATABRICKS_SOURCE' && !databricksHttpPath) {
      setFormError('Pick a workspace and a warehouse — the http_path is derived, never typed.');
      return;
    }
    // Fail-closed S3 guard: a placeholder source must never reach the API.
    if (
      sourceType === 'S3' &&
      (!s3Bucket.trim() || !s3AccessKeyId.trim() || !s3SecretAccessKey.trim())
    ) {
      setFormError('Bucket, access key ID and secret access key are required for S3 sources.');
      return;
    }
    try {
      // Provide minimal valid configs based on source_type and schedule_type
      let sourceConfig: Record<string, unknown> = {};
      if (sourceType === 'S3') {
        sourceConfig = {
          bucket: s3Bucket.trim(),
          ...(s3Prefix.trim() ? { prefix: s3Prefix.trim() } : {}),
          ...(s3Endpoint.trim() ? { endpoint_url: s3Endpoint.trim() } : {}),
          access_key_id: s3AccessKeyId.trim(),
          secret_access_key: s3SecretAccessKey.trim(),
          region: 'us-east-1',
        };
      } else if (sourceType === 'GCS') {
        sourceConfig = { bucket: 'placeholder-bucket' }; // Will need proper form later
      } else if (sourceType === 'AZURE_BLOB') {
        sourceConfig = { account_name: 'placeholder', container: 'placeholder' };
      } else if (sourceType === 'HTTP' || sourceType === 'HTTPS') {
        sourceConfig = { base_url: 'https://example.com' };
      } else if (sourceType === 'FTP' || sourceType === 'SFTP') {
        sourceConfig = { host: 'example.com' };
      } else if (sourceType === 'DATABASE') {
        sourceConfig = { host: 'localhost', database: 'placeholder' };
      } else if (sourceType === 'SNOWFLAKE_SOURCE') {
        sourceConfig = { host: 'placeholder.snowflakecomputing.com', database: 'PLACEHOLDER', schema: 'PUBLIC' };
      } else if (sourceType === 'BIGQUERY_SOURCE') {
        sourceConfig = { project_id: 'placeholder-project', dataset_id: 'placeholder_dataset' };
      } else if (sourceType === 'DATABRICKS_SOURCE') {
        // 6.8 — the picker's derived values are the stored contract.
        sourceConfig = {
          host: databricksHost,
          http_path: databricksHttpPath,
          catalog,
          schema,
        };
      } else if (sourceType === 'ATHENA_SOURCE') {
        sourceConfig = { database: 'placeholder_db', s3_staging_dir: 's3://placeholder-bucket/athena-results/' };
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
        credential_ref: credentialRef || undefined,
      });
      navigate(`/scheduled-ingestions/${schedule.id}`);
    } catch {
      // Error handled by mutation (notification toast) — W12.9 removed
      // the redundant console.error.
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
            <option value="SNOWFLAKE_SOURCE">Snowflake Source</option>
            <option value="BIGQUERY_SOURCE">BigQuery Source</option>
            <option value="DATABRICKS_SOURCE">Databricks Source</option>
            <option value="ATHENA_SOURCE">Athena Source</option>
          </select>
        </div>

        {sourceType === 'S3' && (
          <div className="form-group">
            <label htmlFor="s3_bucket">
              Bucket <span className="required">*</span>
            </label>
            <input
              id="s3_bucket"
              type="text"
              value={s3Bucket}
              onChange={(e) => setS3Bucket(e.target.value)}
              required
              placeholder="e.g., my-source-bucket"
            />
            <label htmlFor="s3_prefix">Prefix</label>
            <input
              id="s3_prefix"
              type="text"
              value={s3Prefix}
              onChange={(e) => setS3Prefix(e.target.value)}
              placeholder="e.g., in/ (optional)"
            />
            <label htmlFor="s3_endpoint">Endpoint URL</label>
            <input
              id="s3_endpoint"
              type="text"
              value={s3Endpoint}
              onChange={(e) => setS3Endpoint(e.target.value)}
              placeholder="e.g., http://minio-test:9000 (optional; for S3-compatible stores)"
            />
            <label htmlFor="s3_access_key_id">
              Access Key ID <span className="required">*</span>
            </label>
            <input
              id="s3_access_key_id"
              type="text"
              value={s3AccessKeyId}
              onChange={(e) => setS3AccessKeyId(e.target.value)}
              required
              placeholder="e.g., minio"
            />
            <label htmlFor="s3_secret_access_key">
              Secret Access Key <span className="required">*</span>
            </label>
            <input
              id="s3_secret_access_key"
              type="password"
              value={s3SecretAccessKey}
              onChange={(e) => setS3SecretAccessKey(e.target.value)}
              required
              placeholder="••••••••"
            />
            <small className="form-help">
              S3-compatible object stores (MinIO, etc.) go in Endpoint URL; leave it
              empty for AWS S3 itself.
            </small>
          </div>
        )}

        {sourceType === 'DATABRICKS_SOURCE' && (
          <div className="form-group">
            {/* 6.8 (design D8) — the workspace+warehouse picker; the stored
                http_path is the DERIVED value, never a hand-typed string. */}
            <DatabricksWarehousePicker
              value={databricksHttpPath}
              onChange={setDatabricksHttpPath}
              onHostChange={setDatabricksHost}
            />
            <label htmlFor="catalog">
              Catalog <span className="required">*</span>
            </label>
            <input
              id="catalog"
              type="text"
              value={catalog}
              onChange={(e) => setCatalog(e.target.value)}
              required
              placeholder="main"
            />
            <label htmlFor="schema">
              Schema <span className="required">*</span>
            </label>
            <input
              id="schema"
              type="text"
              value={schema}
              onChange={(e) => setSchema(e.target.value)}
              required
              placeholder="default"
            />
          </div>
        )}

        {formError && (
          <div className="form-error" role="alert">
            {formError}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="credential_ref">Credential Reference</label>
          <input
            id="credential_ref"
            type="text"
            value={credentialRef}
            onChange={(e) => setCredentialRef(e.target.value)}
            placeholder="arn:aws:secretsmanager:... or prefect://block-name"
          />
          <small className="form-help">
            AWS Secrets Manager ARN or Prefect block reference for dlt credentials.
            Leave empty to use inline credentials from source config.
          </small>
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
