/**
 * AlertingRuleManager (Phase 240.4.A.4).
 *
 * CRUD UI for ``DQAlertingRule`` (TENANT_ADMIN-only).  Channel-config
 * editor for email / Slack / webhook / PagerDuty with field-level
 * validation: each channel's required keys (e.g. ``recipients`` for
 * EMAIL, ``webhook_url`` for SLACK / WEBHOOK, ``service_key`` for
 * PAGERDUTY) are surfaced as required form inputs.
 */

import { useMemo, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useAuthStore } from '../../auth/store/authStore';
import {
  useCreateDQAlertingRule,
  useDeleteDQAlertingRule,
  useDQAlertingRules,
  useUpdateDQAlertingRule,
} from '../hooks/useDQ';
import {
  DQ_ALERT_CHANNELS,
  DQAlertChannel,
  type DQAlertingRule,
  type DQComparisonOperator,
} from '../../../shared/types/dq';
import './DQRunResultsViewer.css';

const COMPARISON_OPERATORS: DQComparisonOperator[] = [
  '<',
  '<=',
  '>',
  '>=',
  '==',
  '!=',
];

const SEVERITIES: Array<'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'> = [
  'CRITICAL',
  'HIGH',
  'MEDIUM',
  'LOW',
];

interface FormState {
  id?: string;            // present when editing existing rule
  asset_id: string;
  name: string;
  description: string;
  metric_type: string;
  threshold: string;
  comparison_operator: DQComparisonOperator;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  alert_channels: DQAlertChannel[];
  channel_config: Record<string, string>;
  enabled: boolean;
}

const blankForm: FormState = {
  asset_id: '',
  name: '',
  description: '',
  metric_type: 'quality_score',
  threshold: '',
  comparison_operator: '<',
  severity: 'MEDIUM',
  alert_channels: [DQAlertChannel.EMAIL],
  channel_config: {},
  enabled: true,
};

/**
 * Per-channel required-key inventory.  Used to drive the field-level
 * validation in the form: the channel-config editor surfaces a text
 * input per required key for each enabled channel.  Mirror the
 * backend ``hub/apps/dq/clients/`` payload contracts.
 */
const CHANNEL_REQUIRED_KEYS: Record<DQAlertChannel, string[]> = {
  [DQAlertChannel.EMAIL]: ['recipients'],
  [DQAlertChannel.SLACK]: ['webhook_url'],
  [DQAlertChannel.WEBHOOK]: ['webhook_url'],
  [DQAlertChannel.PAGERDUTY]: ['service_key'],
};

export function AlertingRuleManager() {
  const { user } = useAuthStore();
  const isTenantAdmin = user?.roles?.includes('TENANT_ADMIN') ?? false;
  const isPlatformAdmin = user?.roles?.includes('PLATFORM_ADMIN') ?? false;
  const canEdit = isTenantAdmin || isPlatformAdmin;

  const { data, isLoading, error, refetch } = useDQAlertingRules();
  const createMutation = useCreateDQAlertingRule();
  const updateMutation = useUpdateDQAlertingRule();
  const deleteMutation = useDeleteDQAlertingRule();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(blankForm);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<DQAlertingRule | null>(null);

  const rules = data?.results ?? [];

  const requiredChannelKeys = useMemo(() => {
    const keys: string[] = [];
    for (const channel of form.alert_channels) {
      keys.push(...(CHANNEL_REQUIRED_KEYS[channel] ?? []));
    }
    return Array.from(new Set(keys));
  }, [form.alert_channels]);

  const startCreate = () => {
    setForm(blankForm);
    setValidationError(null);
    setShowForm(true);
  };

  const startEdit = (rule: DQAlertingRule) => {
    setForm({
      id: rule.id,
      asset_id: rule.asset ?? '',
      name: rule.name,
      description: rule.description,
      metric_type: rule.metric_type,
      threshold: String(rule.threshold),
      comparison_operator: rule.comparison_operator,
      severity: rule.severity,
      alert_channels: rule.alert_channels,
      channel_config: Object.fromEntries(
        Object.entries(rule.channel_config).map(([k, v]) => [k, String(v)]),
      ),
      enabled: rule.enabled,
    });
    setValidationError(null);
    setShowForm(true);
  };

  const cancelForm = () => {
    setShowForm(false);
    setForm(blankForm);
    setValidationError(null);
  };

  const validate = (): string | null => {
    if (!form.name.trim()) return 'Rule name is required';
    if (form.alert_channels.length === 0) return 'Select at least one alert channel';
    // ``Number("")`` is 0 in JS; reject empty string explicitly so a
    // missing threshold doesn't silently submit as 0.
    if (form.threshold.trim() === '') return 'Threshold is required';
    const thresholdNum = Number(form.threshold);
    if (!Number.isFinite(thresholdNum)) return 'Threshold must be a number';
    for (const key of requiredChannelKeys) {
      if (!form.channel_config[key] || !form.channel_config[key].trim()) {
        return `Channel config: ${key} is required`;
      }
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate();
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(null);

    const payload = {
      asset_id: form.asset_id.trim() || undefined,
      name: form.name.trim(),
      description: form.description.trim(),
      metric_type: form.metric_type.trim() || 'quality_score',
      threshold: Number(form.threshold),
      comparison_operator: form.comparison_operator,
      severity: form.severity,
      alert_channels: form.alert_channels,
      channel_config: form.channel_config,
      enabled: form.enabled,
    };

    if (form.id) {
      updateMutation.mutate(
        { id: form.id, data: payload },
        { onSuccess: () => setShowForm(false) },
      );
    } else {
      createMutation.mutate(payload, { onSuccess: () => setShowForm(false) });
    }
  };

  const toggleChannel = (channel: DQAlertChannel) => {
    setForm((f) => {
      const next = f.alert_channels.includes(channel)
        ? f.alert_channels.filter((c) => c !== channel)
        : [...f.alert_channels, channel];
      return { ...f, alert_channels: next };
    });
  };

  const updateChannelConfig = (key: string, value: string) => {
    setForm((f) => ({
      ...f,
      channel_config: { ...f.channel_config, [key]: value },
    }));
  };

  if (!canEdit) {
    return (
      <div className="dq-results-viewer" data-testid="alerting-rule-manager">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Data Quality', href: '/dq' },
            { label: 'Alerting Rules' },
          ]}
        />
        <EmptyState
          title="Tenant admin access required"
          message="Only TENANT_ADMIN or PLATFORM_ADMIN can create or edit alerting rules."
        />
      </div>
    );
  }

  return (
    <div className="dq-results-viewer" data-testid="alerting-rule-manager">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Data Quality', href: '/dq' },
          { label: 'Alerting Rules' },
        ]}
      />

      <div className="dq-results-header">
        <h1>DQ Alerting Rules</h1>
        <p className="dq-results-subtitle">
          Manage threshold-based alerts that fire on every DQ run.
        </p>
        <div>
          <Button onClick={startCreate} data-testid="rule-new-btn">
            New rule
          </Button>
        </div>
      </div>

      {showForm && (
        <form
          className="alerting-rule-form"
          onSubmit={handleSubmit}
          data-testid="rule-form"
          noValidate
        >
          <h3>{form.id ? 'Edit alerting rule' : 'New alerting rule'}</h3>
          <div className="filter-group">
            <label htmlFor="rule-name">Name *</label>
            <input
              id="rule-name"
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div className="filter-group">
            <label htmlFor="rule-desc">Description</label>
            <textarea
              id="rule-desc"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="filter-group">
            <label htmlFor="rule-asset">Asset ID (optional)</label>
            <input
              id="rule-asset"
              type="text"
              value={form.asset_id}
              onChange={(e) => setForm({ ...form, asset_id: e.target.value })}
            />
          </div>
          <div className="filter-group">
            <label htmlFor="rule-metric">Metric type</label>
            <input
              id="rule-metric"
              type="text"
              value={form.metric_type}
              onChange={(e) => setForm({ ...form, metric_type: e.target.value })}
            />
          </div>
          <div className="filter-group">
            <label htmlFor="rule-threshold">Threshold *</label>
            <input
              id="rule-threshold"
              type="number"
              step="0.01"
              value={form.threshold}
              onChange={(e) => setForm({ ...form, threshold: e.target.value })}
              required
            />
          </div>
          <div className="filter-group">
            <label htmlFor="rule-op">Operator</label>
            <select
              id="rule-op"
              value={form.comparison_operator}
              onChange={(e) =>
                setForm({
                  ...form,
                  comparison_operator: e.target.value as DQComparisonOperator,
                })
              }
            >
              {COMPARISON_OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="rule-severity">Severity</label>
            <select
              id="rule-severity"
              value={form.severity}
              onChange={(e) =>
                setForm({
                  ...form,
                  severity: e.target.value as FormState['severity'],
                })
              }
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <fieldset className="filter-group">
            <legend>Alert channels *</legend>
            {DQ_ALERT_CHANNELS.map((channel) => (
              <label key={channel} style={{ display: 'block' }}>
                <input
                  type="checkbox"
                  checked={form.alert_channels.includes(channel)}
                  onChange={() => toggleChannel(channel)}
                />{' '}
                {channel}
              </label>
            ))}
          </fieldset>

          {requiredChannelKeys.length > 0 && (
            <fieldset className="filter-group">
              <legend>Channel configuration *</legend>
              {requiredChannelKeys.map((key) => (
                <div key={key} className="filter-group">
                  <label htmlFor={`channel-cfg-${key}`}>{key}</label>
                  <input
                    id={`channel-cfg-${key}`}
                    type="text"
                    value={form.channel_config[key] ?? ''}
                    onChange={(e) => updateChannelConfig(key, e.target.value)}
                    required
                  />
                </div>
              ))}
            </fieldset>
          )}

          <div className="filter-group">
            <label>
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />{' '}
              Enabled
            </label>
          </div>

          {validationError && (
            <p
              className="form-error"
              role="alert"
              data-testid="rule-form-error"
            >
              {validationError}
            </p>
          )}

          <div className="filter-group">
            <Button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {form.id ? 'Save' : 'Create'}
            </Button>
            <Button variant="secondary" onClick={cancelForm} type="button">
              Cancel
            </Button>
          </div>
        </form>
      )}

      {isLoading ? (
        <ListPageSkeleton />
      ) : error ? (
        <ErrorDisplay
          error={error}
          title="Failed to load alerting rules"
          onRetry={() => refetch()}
        />
      ) : rules.length === 0 ? (
        <EmptyState
          title="No alerting rules"
          message="Create a rule to be notified when a DQ metric crosses a threshold."
        />
      ) : (
        <div className="dq-run-list-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Metric</th>
                <th>Threshold</th>
                <th>Severity</th>
                <th>Channels</th>
                <th>Enabled</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} data-testid={`rule-row-${rule.id}`}>
                  <td>{rule.name}</td>
                  <td>{rule.metric_type}</td>
                  <td>
                    {rule.comparison_operator} {rule.threshold}
                  </td>
                  <td>
                    <span
                      className={`status-badge status-${rule.severity.toLowerCase()}`}
                    >
                      {rule.severity}
                    </span>
                  </td>
                  <td>{rule.alert_channels.join(', ')}</td>
                  <td>{rule.enabled ? '✅' : '❌'}</td>
                  <td>
                    <Button
                      variant="secondary"
                      onClick={() => startEdit(rule)}
                      data-testid={`rule-edit-${rule.id}`}
                    >
                      Edit
                    </Button>{' '}
                    <Button
                      variant="danger"
                      onClick={() => setConfirmDelete(rule)}
                      data-testid={`rule-delete-${rule.id}`}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDialog
          isOpen={!!confirmDelete}
          title="Delete alerting rule?"
          message={`Are you sure you want to delete the alerting rule "${confirmDelete.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          variant="danger"
          onConfirm={() => {
            deleteMutation.mutate(confirmDelete.id);
            setConfirmDelete(null);
          }}
          onClose={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}
