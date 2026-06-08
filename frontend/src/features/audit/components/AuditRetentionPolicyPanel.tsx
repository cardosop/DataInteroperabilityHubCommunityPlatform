/**
 * Phase 234.5 — TENANT_ADMIN panel for per-event-type audit retention overrides.
 *
 * Renders the list of ``AuditEventRetentionPolicy`` rows for the current
 * tenant + an inline "add policy" form. Each row can be edited (toggle
 * ``enabled``, change ``retention_days`` / ``regulation_keys``) or
 * deleted. The backend ``clean()`` is the source of truth — when the
 * operator supplies both ``regulation_keys`` and ``retention_days``,
 * the server returns the registry-derived value.
 */

import { useState, type FormEvent } from 'react';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { normalizeError } from '../../../shared/utils/errorUtils';
import type {
  AuditEventRetentionPolicy,
  AuditEventRetentionPolicyInput,
} from '../../../shared/types/audit';
import {
  useAuditEventRetentionPolicies,
  useCreateAuditEventRetentionPolicy,
  useDeleteAuditEventRetentionPolicy,
  useUpdateAuditEventRetentionPolicy,
} from '../hooks/useAudit';

const KNOWN_REGULATION_KEYS = ['GDPR', 'UK_GDPR', 'LGPD', 'CCPA', 'CPA_COLORADO'] as const;

interface NewPolicyFormState {
  event_type: string;
  retention_days: string;
  regulation_keys: string[];
}

const EMPTY_NEW_POLICY: NewPolicyFormState = {
  event_type: '',
  retention_days: '',
  regulation_keys: [],
};

export function AuditRetentionPolicyPanel() {
  const { data, isLoading, error, refetch } = useAuditEventRetentionPolicies();
  const createMutation = useCreateAuditEventRetentionPolicy();
  const updateMutation = useUpdateAuditEventRetentionPolicy();
  const deleteMutation = useDeleteAuditEventRetentionPolicy();

  const [newPolicy, setNewPolicy] = useState<NewPolicyFormState>(EMPTY_NEW_POLICY);
  const [formError, setFormError] = useState<string | null>(null);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorDisplay error={normalizeError(error)} onRetry={() => refetch()} />;
  }

  const policies: AuditEventRetentionPolicy[] = data?.results ?? [];

  function buildInput(state: NewPolicyFormState): AuditEventRetentionPolicyInput | null {
    const event_type = state.event_type.trim();
    if (!event_type) {
      setFormError('Event type is required.');
      return null;
    }
    const retention_days_str = state.retention_days.trim();
    const regulation_keys = state.regulation_keys.filter((k) => k.trim());
    if (!retention_days_str && regulation_keys.length === 0) {
      setFormError('Provide retention_days or at least one regulation key.');
      return null;
    }
    const input: AuditEventRetentionPolicyInput = { event_type, regulation_keys };
    if (retention_days_str) {
      const n = Number.parseInt(retention_days_str, 10);
      if (Number.isNaN(n) || n < 1) {
        setFormError('retention_days must be a positive integer.');
        return null;
      }
      input.retention_days = n;
    }
    return input;
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const input = buildInput(newPolicy);
    if (!input) return;
    try {
      await createMutation.mutateAsync(input);
      setNewPolicy(EMPTY_NEW_POLICY);
    } catch (err) {
      setFormError(normalizeError(err).message ?? 'Failed to create policy.');
    }
  }

  async function handleToggleEnabled(policy: AuditEventRetentionPolicy) {
    await updateMutation.mutateAsync({
      id: policy.id,
      input: { enabled: !policy.enabled },
    });
  }

  async function handleDelete(policy: AuditEventRetentionPolicy) {
    if (!window.confirm(`Delete retention policy for "${policy.event_type}"?`)) {
      return;
    }
    await deleteMutation.mutateAsync(policy.id);
  }

  return (
    <section className="tenant-settings-audit" data-testid="tenant-settings-audit">
      <h2>Audit Retention Policies</h2>
      <p className="tenant-settings-description">
        Per-event-type overrides for the audit-event retention window. When a
        policy applies to a tenant + event-type pair, the ``archive_old_audit_events``
        sweep uses its <code>retention_days</code> (or the regulation-derived
        equivalent) instead of the global default. Empty list = global default
        applies to every event type.
      </p>

      <form className="audit-retention-form" onSubmit={handleCreate}>
        <h3>Add Policy</h3>
        <div className="audit-retention-form-row">
          <label htmlFor="audit-ret-event-type">Event type</label>
          <input
            id="audit-ret-event-type"
            type="text"
            placeholder="e.g. BREACH_INCIDENT_OPENED"
            value={newPolicy.event_type}
            onChange={(e) =>
              setNewPolicy((p) => ({ ...p, event_type: e.target.value }))
            }
          />
        </div>
        <div className="audit-retention-form-row">
          <label htmlFor="audit-ret-days">Retention days (optional)</label>
          <input
            id="audit-ret-days"
            type="number"
            min={1}
            placeholder="e.g. 2555 (7y)"
            value={newPolicy.retention_days}
            onChange={(e) =>
              setNewPolicy((p) => ({ ...p, retention_days: e.target.value }))
            }
          />
        </div>
        <div className="audit-retention-form-row">
          <label>Regulation keys</label>
          <div className="audit-retention-checkboxes">
            {KNOWN_REGULATION_KEYS.map((key) => (
              <label key={key} className="audit-retention-checkbox">
                <input
                  type="checkbox"
                  checked={newPolicy.regulation_keys.includes(key)}
                  onChange={(e) =>
                    setNewPolicy((p) => ({
                      ...p,
                      regulation_keys: e.target.checked
                        ? [...p.regulation_keys, key]
                        : p.regulation_keys.filter((k) => k !== key),
                    }))
                  }
                />
                {key}
              </label>
            ))}
          </div>
        </div>
        {formError && <p className="audit-retention-form-error">{formError}</p>}
        <Button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? 'Creating…' : 'Add Policy'}
        </Button>
      </form>

      <h3>Active Policies ({policies.length})</h3>
      {policies.length === 0 ? (
        <p className="audit-retention-empty">
          No per-event-type overrides configured. Global retention applies to every event.
        </p>
      ) : (
        <table className="audit-retention-table">
          <thead>
            <tr>
              <th>Event type</th>
              <th>Retention (days)</th>
              <th>Regulation keys</th>
              <th>Enabled</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id} data-testid={`audit-retention-row-${p.event_type}`}>
                <td><code>{p.event_type}</code></td>
                <td>{p.retention_days ?? '—'}</td>
                <td>
                  {p.regulation_keys.length === 0
                    ? '—'
                    : p.regulation_keys.join(', ')}
                </td>
                <td>
                  <label className="audit-retention-toggle">
                    <input
                      type="checkbox"
                      checked={p.enabled}
                      onChange={() => handleToggleEnabled(p)}
                      disabled={updateMutation.isPending}
                    />
                    {p.enabled ? 'Enabled' : 'Disabled'}
                  </label>
                </td>
                <td>{new Date(p.updated_at).toLocaleString()}</td>
                <td>
                  <Button
                    variant="secondary"
                    onClick={() => handleDelete(p)}
                    disabled={deleteMutation.isPending}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
