/**
 * Retention Policy Edit Page
 * Form for editing an existing retention policy
 */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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

    // Read current values from DOM inputs as fallback (handles React state timing issues)
    const formElement = e.currentTarget;
    const getInputValue = (name: string): string | null => {
      const input = formElement.querySelector(`[name="${name}"]`) as
        | HTMLInputElement
        | HTMLTextAreaElement
        | HTMLSelectElement
        | null;
      if (!input) {
        return null; // Return null only if input not found
      }
      if (input.type === 'checkbox') {
        return (input as HTMLInputElement).checked ? 'true' : '';
      }
      // Return the actual value (even if empty string) - this is what user typed
      // For controlled inputs, input.value reflects the current DOM state
      return input.value;
    };

    const getNumberValue = (name: string): number | undefined => {
      const value = getInputValue(name);
      if (value === null || value === '') {
        return undefined;
      }
      const parsed = parseInt(value, 10);
      return isNaN(parsed) ? undefined : parsed;
    };

    const getCheckboxValue = (name: string): boolean | undefined => {
      const input = formElement.querySelector(`[name="${name}"]`) as HTMLInputElement | null;
      if (input) {
        return input.checked;
      }
      return undefined; // Return undefined if not found, so fallback to state works
    };

    // Get current form values - prefer React state (most reliable) but fallback to DOM
    // Get current form values - prefer DOM values (most up-to-date) but fallback to state
    // For controlled inputs, DOM value reflects React state, but DOM updates immediately
    // while React state updates are async. Reading from DOM ensures we get the latest value.
    const nameFromDom = getInputValue('name');
    // Always prefer DOM value if available (most up-to-date), fallback to state only if DOM not found
    // This ensures we read the current input value even if React state hasn't updated yet
    // For controlled inputs, input.value always reflects the current React state value
    const currentName = nameFromDom !== null ? nameFromDom : form.name || '';

    const descFromDom = getInputValue('description');
    const currentDescription = descFromDom !== null ? descFromDom : form.description || '';
    const assetIdFromDom = getInputValue('asset_id');
    const currentAssetId = assetIdFromDom !== null ? assetIdFromDom : form.asset_id || '';
    const datasetIdFromDom = getInputValue('dataset_id');
    const currentDatasetId = datasetIdFromDom !== null ? datasetIdFromDom : form.dataset_id || '';
    const fileIdFromDom = getInputValue('file_id');
    const currentFileId = fileIdFromDom !== null ? fileIdFromDom : form.file_id || '';
    const policyTypeFromDom = getInputValue('policy_type');
    const currentPolicyType = (
      policyTypeFromDom !== null
        ? policyTypeFromDom
        : form.policy_type || RetentionPolicyTypeEnum.TIME_BASED
    ) as RetentionPolicyType;
    const retentionPeriodFromDom = getNumberValue('retention_period_days');
    const currentRetentionPeriod =
      retentionPeriodFromDom !== undefined ? retentionPeriodFromDom : form.retention_period_days;
    const eventTriggerFromDom = getInputValue('event_trigger');
    const currentEventTrigger =
      eventTriggerFromDom !== null ? eventTriggerFromDom : form.event_trigger || '';
    const actionFromDom = getInputValue('action');
    const currentAction = (
      actionFromDom !== null ? actionFromDom : form.action || RetentionActionEnum.SOFT_DELETE
    ) as RetentionAction;
    const gracePeriodFromDom = getNumberValue('grace_period_days');
    const currentGracePeriod =
      gracePeriodFromDom !== undefined ? gracePeriodFromDom : form.grace_period_days;
    const legalHoldFromDom = getCheckboxValue('legal_hold');
    const currentLegalHold =
      legalHoldFromDom !== undefined ? legalHoldFromDom : (form.legal_hold ?? false);
    const legalHoldReasonFromDom = getInputValue('legal_hold_reason');
    const currentLegalHoldReason =
      legalHoldReasonFromDom !== null ? legalHoldReasonFromDom : form.legal_hold_reason || '';
    const legalHoldExpiresFromDom = getInputValue('legal_hold_expires_at');
    const currentLegalHoldExpires =
      legalHoldExpiresFromDom !== null ? legalHoldExpiresFromDom : form.legal_hold_expires_at || '';
    const enabledFromDom = getCheckboxValue('enabled');
    const currentEnabled = enabledFromDom !== undefined ? enabledFromDom : (form.enabled ?? true);

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
          message: 'At least one of Asset ID, Dataset ID, or File ID is required',
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
      <button
        type="button"
        className="btn-back"
        onClick={() => navigate(`/governance/retention/${id}`)}
      >
        ← Back to Retention Policy
      </button>
      <h1>Edit retention policy</h1>

      <form className="governance-retention-policy-form" onSubmit={handleSubmit}>
        {(submitError || updateMutation.error) && (
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
            onChange={(e) => setForm({ ...form, name: e.target.value })}
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
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Optional description"
            rows={3}
          />
        </div>

        <div className="form-group">
          <label>Resource (at least one required)</label>
          <div className="resource-inputs">
            <input
              type="text"
              name="asset_id"
              placeholder="Asset ID (optional)"
              value={form.asset_id || ''}
              onChange={(e) => setForm({ ...form, asset_id: e.target.value })}
            />
            <input
              type="text"
              name="dataset_id"
              placeholder="Dataset ID (optional)"
              value={form.dataset_id || ''}
              onChange={(e) => setForm({ ...form, dataset_id: e.target.value })}
            />
            <input
              type="text"
              name="file_id"
              placeholder="File ID (optional)"
              value={form.file_id || ''}
              onChange={(e) => setForm({ ...form, file_id: e.target.value })}
            />
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
            name="action"
            value={form.action || RetentionActionEnum.SOFT_DELETE}
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
                name="legal_hold_reason"
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
                name="legal_hold_expires_at"
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
              name="enabled"
              checked={form.enabled ?? true}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enabled
          </label>
        </div>

        <div className="form-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate(`/governance/retention/${id}`)}
          >
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Updating...' : 'Update retention policy'}
          </button>
        </div>
      </form>
    </div>
  );
}
