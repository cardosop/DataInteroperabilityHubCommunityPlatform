/**
 * Retention Policy Edit Page
 * Form for editing an existing retention policy.
 * Uses AssetPicker, DatasetPicker, FilePicker for resource selection (task 29.69.6.2).
 */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  AssetPicker,
  DatasetPicker,
  FilePicker,
} from '../../../shared/components/pickers';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import type {
  RetentionAction,
  RetentionPolicyType,
  RetentionPolicyUpdateRequest,
} from '../../../shared/types/governanceRetention';
import {
  RetentionAction as RetentionActionEnum,
  RetentionPolicyType as RetentionPolicyTypeEnum,
} from '../../../shared/types/governanceRetention';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useRetentionPolicy, useUpdateRetentionPolicy } from '../hooks/useRetention';
import './RetentionPolicyEditPage.css';
import { Button } from '../../../shared/components/Button';

export function RetentionPolicyEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: policy, isLoading, error, refetch } = useRetentionPolicy(id || null);
  const updateMutation = useUpdateRetentionPolicy();
  const [form, setForm] = useState<Partial<RetentionPolicyUpdateRequest>>({});
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Initialize form when policy loads
  useEffect(() => {
    if (policy && !initialized) {
      setForm({
        id: policy.id,
        name: policy.name,
        description: policy.description || '',
        asset_id: policy.asset || '',
        dataset_id: policy.dataset || '',
        file_id: policy.file || '',
        policy_type: policy.policy_type,
        retention_period_days: policy.retention_period_days || undefined,
        event_trigger: policy.event_trigger || '',
        action: policy.action,
        grace_period_days: policy.grace_period_days,
        legal_hold: policy.legal_hold,
        legal_hold_reason: policy.legal_hold_reason || '',
        legal_hold_expires_at: policy.legal_hold_expires_at || '',
        enabled: policy.enabled,
      });
      setInitialized(true);
    }
  }, [policy, initialized]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitError(null);

    if (!id) return;

    const currentName = form.name || '';
    const currentDescription = form.description || '';
    const currentAssetId = form.asset_id || '';
    const currentDatasetId = form.dataset_id || '';
    const currentFileId = form.file_id || '';
    const currentPolicyType = (form.policy_type || RetentionPolicyTypeEnum.TIME_BASED) as RetentionPolicyType;
    const currentRetentionPeriod = form.retention_period_days;
    const currentEventTrigger = form.event_trigger || '';
    const currentAction = (form.action || RetentionActionEnum.SOFT_DELETE) as RetentionAction;
    const currentGracePeriod = form.grace_period_days;
    const currentLegalHold = form.legal_hold ?? false;
    const currentLegalHoldReason = form.legal_hold_reason || '';
    const currentLegalHoldExpires = form.legal_hold_expires_at || '';
    const currentEnabled = form.enabled ?? true;

    // Validation
    if (!currentName.trim()) {
      setSubmitError({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Name is required',
          http_status: 400,
          request_id: 'unknown',
          timestamp: new Date().toISOString(),
        },
      });
      return;
    }

    const asset_id = currentAssetId.trim() || undefined;
    const dataset_id = currentDatasetId.trim() || undefined;
    const file_id = currentFileId.trim() || undefined;

    if (!asset_id && !dataset_id && !file_id) {
      setSubmitError({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'At least one of Asset, Dataset, or File is required',
          http_status: 400,
          request_id: 'unknown',
          timestamp: new Date().toISOString(),
        },
      });
      return;
    }

    if (currentPolicyType === RetentionPolicyTypeEnum.TIME_BASED && !currentRetentionPeriod) {
      setSubmitError({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Retention period days is required for time-based policies',
          http_status: 400,
          request_id: 'unknown',
          timestamp: new Date().toISOString(),
        },
      });
      return;
    }

    if (currentPolicyType === RetentionPolicyTypeEnum.EVENT_BASED && !currentEventTrigger.trim()) {
      setSubmitError({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Event trigger is required for event-based policies',
          http_status: 400,
          request_id: 'unknown',
          timestamp: new Date().toISOString(),
        },
      });
      return;
    }

    try {
      const payload: RetentionPolicyUpdateRequest = {
        id,
        name: currentName.trim(),
        description: currentDescription.trim() || undefined,
        asset_id,
        dataset_id,
        file_id,
        policy_type: currentPolicyType,
        retention_period_days: currentRetentionPeriod,
        event_trigger: currentEventTrigger.trim() || undefined,
        action: currentAction,
        grace_period_days: currentGracePeriod,
        legal_hold: currentLegalHold,
        legal_hold_reason: currentLegalHoldReason.trim() || undefined,
        legal_hold_expires_at: currentLegalHoldExpires || undefined,
        enabled: currentEnabled,
      };
      await updateMutation.mutateAsync(payload);
      navigate(`/governance/retention/${id}`);
    } catch (err) {
      setSubmitError(normalizeError(err));
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading retention policy..." />;
  }

  if (error || !policy) {
    return (
      <ErrorDisplay
        error={error || new Error('Retention policy not found')}
        title="Failed to load retention policy"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="governance-retention-policy-edit-page">
      <Button
 variant="ghost"
 onClick={() => navigate(`/governance/retention/${id}`)}>
        ← Back to Retention Policy
      </Button>
      <h1>Edit retention policy</h1>

      <form className="governance-retention-policy-form" onSubmit={handleSubmit}>
        {!!(submitError || updateMutation.error) && (
          <ErrorDisplay
            error={submitError || updateMutation.error}
            title="Failed to update retention policy"
          />
        )}

        <div className="form-group">
          <label htmlFor="name">
            Name <span className="required">*</span>
          </label>
          <input
            id="name"
            name="name"
            type="text"
            value={form.name || ''}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            required
            placeholder="e.g., 30 Day Retention Policy"
          />
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            value={form.description || ''}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            placeholder="Optional description"
            rows={3}
          />
        </div>

        <div className="form-group">
          <label>Resource (at least one required)</label>
          <div className="resource-inputs retention-picker-row">
            <div className="retention-picker-field">
              <label htmlFor="retention-asset-picker">Asset (optional)</label>
              <AssetPicker
                value={form.asset_id || null}
                onChange={(id) => setForm((prev) => ({ ...prev, asset_id: id ?? '' }))}
                placeholder="Search and select an asset..."
                data-testid="retention-asset-picker"
              />
            </div>
            <div className="retention-picker-field">
              <label htmlFor="retention-dataset-picker">Dataset (optional)</label>
              <DatasetPicker
                value={form.dataset_id || null}
                onChange={(id) => setForm((prev) => ({ ...prev, dataset_id: id ?? '' }))}
                placeholder="Search and select a dataset..."
                assetId={form.asset_id || undefined}
                data-testid="retention-dataset-picker"
              />
            </div>
            <div className="retention-picker-field">
              <label htmlFor="retention-file-picker">File (optional)</label>
              <FilePicker
                value={form.file_id || null}
                onChange={(id) => setForm((prev) => ({ ...prev, file_id: id ?? '' }))}
                placeholder="Search and select a file..."
                assetId={form.asset_id || undefined}
                datasetId={form.dataset_id || undefined}
                data-testid="retention-file-picker"
              />
            </div>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="policy_type">
            Policy Type <span className="required">*</span>
          </label>
          <select
            id="policy_type"
            name="policy_type"
            value={form.policy_type || RetentionPolicyTypeEnum.TIME_BASED}
            onChange={(e) =>
              setForm({
                ...form,
                policy_type: e.target.value as RetentionPolicyType,
              })
            }
            required
          >
            <option value={RetentionPolicyTypeEnum.TIME_BASED}>Time-Based</option>
            <option value={RetentionPolicyTypeEnum.EVENT_BASED}>Event-Based</option>
          </select>
        </div>

        {form.policy_type === RetentionPolicyTypeEnum.TIME_BASED && (
          <div className="form-group">
            <label htmlFor="retention_period_days">
              Retention Period (days) <span className="required">*</span>
            </label>
            <input
              id="retention_period_days"
              name="retention_period_days"
              type="number"
              min="1"
              value={form.retention_period_days || ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  retention_period_days: e.target.value ? parseInt(e.target.value, 10) : undefined,
                })
              }
              required
              placeholder="e.g., 30"
            />
          </div>
        )}

        {form.policy_type === RetentionPolicyTypeEnum.EVENT_BASED && (
          <div className="form-group">
            <label htmlFor="event_trigger">
              Event Trigger <span className="required">*</span>
            </label>
            <input
              id="event_trigger"
              name="event_trigger"
              type="text"
              value={form.event_trigger || ''}
              onChange={(e) => setForm((prev) => ({ ...prev, event_trigger: e.target.value }))}
              required
              placeholder="e.g., contract_expired, project_completed"
            />
          </div>
        )}

        <div className="form-group">
          <label htmlFor="action">Action</label>
          <select
            id="action"
            name="action"
            value={form.action || RetentionActionEnum.SOFT_DELETE}
            onChange={(e) => setForm((prev) => ({ ...prev, action: e.target.value as RetentionAction }))}
          >
            <option value={RetentionActionEnum.SOFT_DELETE}>Soft Delete</option>
            <option value={RetentionActionEnum.HARD_DELETE}>Hard Delete</option>
            <option value={RetentionActionEnum.ARCHIVE}>Archive</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="grace_period_days">Grace Period (days)</label>
          <input
            id="grace_period_days"
            name="grace_period_days"
            type="number"
            min="0"
            value={form.grace_period_days || 30}
            onChange={(e) =>
              setForm({
                ...form,
                grace_period_days: parseInt(e.target.value, 10) || 30,
              })
            }
          />
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              name="legal_hold"
              checked={form.legal_hold || false}
              onChange={(e) => setForm((prev) => ({ ...prev, legal_hold: e.target.checked }))}
            />
            Legal Hold
          </label>
        </div>

        {form.legal_hold && (
          <>
            <div className="form-group">
              <label htmlFor="legal_hold_reason">Legal Hold Reason</label>
              <textarea
                id="legal_hold_reason"
                name="legal_hold_reason"
                value={form.legal_hold_reason || ''}
                onChange={(e) => setForm((prev) => ({ ...prev, legal_hold_reason: e.target.value }))}
                placeholder="Reason for legal hold"
                rows={3}
              />
            </div>
            <div className="form-group">
              <label htmlFor="legal_hold_expires_at">Legal Hold Expires At</label>
              <input
                id="legal_hold_expires_at"
                name="legal_hold_expires_at"
                type="datetime-local"
                value={form.legal_hold_expires_at || ''}
                onChange={(e) => setForm((prev) => ({ ...prev, legal_hold_expires_at: e.target.value }))}
              />
            </div>
          </>
        )}

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              name="enabled"
              checked={form.enabled ?? true}
              onChange={(e) => setForm((prev) => ({ ...prev, enabled: e.target.checked }))}
            />
            Enabled
          </label>
        </div>

        <div className="form-actions">
          <Button
 variant="secondary"
 onClick={() => navigate(`/governance/retention/${id}`)}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={updateMutation.isPending}>
            Update retention policy
          </Button>
        </div>
      </form>
    </div>
  );
}
