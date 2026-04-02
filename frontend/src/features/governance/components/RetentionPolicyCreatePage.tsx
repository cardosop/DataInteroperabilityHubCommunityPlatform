/**
 * Retention Policy Create Page
 * Form for creating a new retention policy.
 * Uses AssetPicker, DatasetPicker, FilePicker for resource selection (task 29.69.6.2).
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AssetPicker,
  DatasetPicker,
  FilePicker,
} from '../../../shared/components/pickers';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import type { ApiError } from '../../../shared/types/api';
import type {
  RetentionAction,
  RetentionPolicyCreateRequest,
  RetentionPolicyType,
} from '../../../shared/types/governanceRetention';
import {
  RetentionAction as RetentionActionEnum,
  RetentionPolicyType as RetentionPolicyTypeEnum,
} from '../../../shared/types/governanceRetention';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useCreateRetentionPolicy } from '../hooks/useRetention';
import './RetentionPolicyCreatePage.css';
import { Button } from '../../../shared/components/Button';

const INITIAL_FORM: RetentionPolicyCreateRequest = {
  name: '',
  description: '',
  asset_id: '',
  dataset_id: '',
  file_id: '',
  policy_type: RetentionPolicyTypeEnum.TIME_BASED,
  retention_period_days: undefined,
  event_trigger: '',
  action: RetentionActionEnum.SOFT_DELETE,
  grace_period_days: 30,
  legal_hold: false,
  legal_hold_reason: '',
  legal_hold_expires_at: '',
  enabled: true,
};

export function RetentionPolicyCreatePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);

  const createMutation = useCreateRetentionPolicy();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    // Validation
    if (!form.name.trim()) {
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

    const asset_id = form.asset_id?.trim() || undefined;
    const dataset_id = form.dataset_id?.trim() || undefined;
    const file_id = form.file_id?.trim() || undefined;

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

    if (form.policy_type === RetentionPolicyTypeEnum.TIME_BASED && !form.retention_period_days) {
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

    if (form.policy_type === RetentionPolicyTypeEnum.EVENT_BASED && !form.event_trigger?.trim()) {
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
      const payload: RetentionPolicyCreateRequest = {
        name: form.name.trim(),
        description: form.description?.trim() || undefined,
        asset_id,
        dataset_id,
        file_id,
        policy_type: form.policy_type,
        retention_period_days: form.retention_period_days,
        event_trigger: form.event_trigger?.trim() || undefined,
        action: form.action,
        grace_period_days: form.grace_period_days,
        legal_hold: form.legal_hold,
        legal_hold_reason: form.legal_hold_reason?.trim() || undefined,
        legal_hold_expires_at: form.legal_hold_expires_at || undefined,
        enabled: form.enabled,
      };
      const created = await createMutation.mutateAsync(payload);
      navigate(`/governance/retention/${created.id}`);
    } catch (err) {
      setSubmitError(normalizeError(err));
    }
  };

  return (
    <div className="governance-retention-policy-create-page">
      <Button variant="ghost" onClick={() => navigate('/governance/retention')}>
        ← Back to Retention Policies
      </Button>
      <h1>Create retention policy</h1>

      <form className="governance-retention-policy-form" onSubmit={handleSubmit}>
        {!!(submitError || createMutation.error) && (
          <ErrorDisplay
            error={submitError || createMutation.error}
            title="Failed to create retention policy"
          />
        )}

        <div className="form-group">
          <label htmlFor="name">
            Name <span className="required">*</span>
          </label>
          <input
            id="name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            placeholder="e.g., 30 Day Retention Policy"
          />
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={form.description || ''}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
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
                onChange={(id) => setForm({ ...form, asset_id: id ?? '' })}
                placeholder="Search and select an asset..."
                data-testid="retention-asset-picker"
              />
            </div>
            <div className="retention-picker-field">
              <label htmlFor="retention-dataset-picker">Dataset (optional)</label>
              <DatasetPicker
                value={form.dataset_id || null}
                onChange={(id) => setForm({ ...form, dataset_id: id ?? '' })}
                placeholder="Search and select a dataset..."
                assetId={form.asset_id || undefined}
                data-testid="retention-dataset-picker"
              />
            </div>
            <div className="retention-picker-field">
              <label htmlFor="retention-file-picker">File (optional)</label>
              <FilePicker
                value={form.file_id || null}
                onChange={(id) => setForm({ ...form, file_id: id ?? '' })}
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
            value={form.policy_type}
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
              type="text"
              value={form.event_trigger || ''}
              onChange={(e) => setForm({ ...form, event_trigger: e.target.value })}
              required
              placeholder="e.g., contract_expired, project_completed"
            />
          </div>
        )}

        <div className="form-group">
          <label htmlFor="action">Action</label>
          <select
            id="action"
            value={form.action}
            onChange={(e) => setForm({ ...form, action: e.target.value as RetentionAction })}
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
            type="number"
            min="0"
            value={form.grace_period_days}
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
              checked={form.legal_hold}
              onChange={(e) => setForm({ ...form, legal_hold: e.target.checked })}
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
                value={form.legal_hold_reason || ''}
                onChange={(e) => setForm({ ...form, legal_hold_reason: e.target.value })}
                placeholder="Reason for legal hold"
                rows={3}
              />
            </div>
            <div className="form-group">
              <label htmlFor="legal_hold_expires_at">Legal Hold Expires At</label>
              <input
                id="legal_hold_expires_at"
                type="datetime-local"
                value={form.legal_hold_expires_at || ''}
                onChange={(e) => setForm({ ...form, legal_hold_expires_at: e.target.value })}
              />
            </div>
          </>
        )}

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enabled
          </label>
        </div>

        <div className="form-actions">
          <Button
 variant="secondary"
 onClick={() => navigate('/governance/retention')}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={createMutation.isPending}>
            Create retention policy
          </Button>
        </div>
      </form>
    </div>
  );
}
