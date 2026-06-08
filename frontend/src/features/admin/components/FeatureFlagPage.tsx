/**
 * Phase 235.1 — PLATFORM_ADMIN per-tenant feature-flag UI.
 *
 * Mounted at /admin/feature-flags. Renders a tabular view (rows =
 * tenants, columns = registry flags) that auto-renders new flags
 * added to `hub/apps/tenants/feature_flag_registry.py` — no code
 * change to this file required when a flag lands.
 *
 * Each cell is a toggle; clicking opens a confirmation dialog
 * demanding a reason (min 10 chars). Sensitive flags
 * (`sensitive=True` in the registry) show "Requires 2nd approval"
 * once submitted and remain pending until a SECOND PLATFORM_ADMIN
 * approves via the approval row.
 *
 * Backend contract:
 *   PUT  /api/v1/admin/tenants/{id}/feature-flags/  (200 / 202 / 400 / 429)
 *   POST /api/v1/admin/feature-flag-approvals/{id}/approve/
 *
 * The page reads the FIRST page of tenants (paginated) and lazily
 * fetches feature-flag state on tenant selection — for a large
 * fleet, holding all (tenant × flag) state in memory at once is
 * needlessly heavy.
 */

import { useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { AdminFeatureFlagRow } from '../services/adminService';
import {
  useAdminTenantFeatureFlags,
  useApproveFeatureFlagFlip,
  useTenants,
  useUpdateAdminTenantFeatureFlags,
} from '../hooks/useAdmin';
import './FeatureFlagPage.css';

interface PendingFlip {
  flag: AdminFeatureFlagRow;
  newValue: boolean;
}

export function FeatureFlagPage() {
  const { data: tenantsData, isLoading: tenantsLoading, error: tenantsError } =
    useTenants({ page_size: 50 });
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const {
    data: flagsData,
    isLoading: flagsLoading,
    error: flagsError,
    refetch: refetchFlags,
  } = useAdminTenantFeatureFlags(selectedTenantId);
  const updateMutation = useUpdateAdminTenantFeatureFlags();
  const approveMutation = useApproveFeatureFlagFlip();

  const [pending, setPending] = useState<PendingFlip | null>(null);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);

  if (tenantsLoading) return <LoadingSpinner />;
  if (tenantsError) return <ErrorDisplay error={tenantsError} />;

  const tenants = tenantsData?.results ?? [];

  function openConfirm(flag: AdminFeatureFlagRow, nextValue: boolean) {
    setPending({ flag, newValue: nextValue });
    setReason('');
    setReasonError(null);
  }

  async function submitConfirm() {
    if (!pending || !selectedTenantId) return;
    const trimmed = reason.trim();
    if (trimmed.length < 10) {
      setReasonError('Reason must be at least 10 characters.');
      return;
    }
    try {
      await updateMutation.mutateAsync({
        tenantId: selectedTenantId,
        flags: {
          [pending.flag.name]: pending.newValue,
        },
        reason: trimmed,
      });
      setPending(null);
      setReason('');
      setReasonError(null);
    } catch {
      // Toast already surfaced by useMutationWithNotification; keep
      // dialog open so the operator can adjust + retry.
    }
  }

  async function approve(approvalId: string) {
    if (!selectedTenantId) return;
    await approveMutation.mutateAsync({ flagId: approvalId, tenantId: selectedTenantId });
    await refetchFlags();
  }

  return (
    <div className="feature-flag-page" data-testid="feature-flag-page">
      <Breadcrumbs
        items={[
          { label: 'Admin', to: '/admin' },
          { label: 'Feature Flags' },
        ]}
      />
      <h1>PLATFORM_ADMIN — Per-Tenant Feature Flags</h1>
      <p className="feature-flag-page__subhead">
        Registry-driven view of every <code>Tenant.*_enabled</code> flag.
        Sensitive flips require a second admin to approve.
      </p>

      <div className="feature-flag-page__tenant-picker">
        <label htmlFor="tenant-select">Tenant</label>
        <select
          id="tenant-select"
          value={selectedTenantId ?? ''}
          onChange={(e) => setSelectedTenantId(e.target.value || null)}
        >
          <option value="">— Select a tenant —</option>
          {tenants.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.slug})
            </option>
          ))}
        </select>
      </div>

      {selectedTenantId && flagsLoading && <LoadingSpinner />}
      {selectedTenantId && flagsError && <ErrorDisplay error={flagsError} />}

      {selectedTenantId && flagsData && (
        <>
          {flagsData.pending_approvals.length > 0 && (
            <section className="feature-flag-page__pending" data-testid="pending-approvals">
              <h2>Pending second-admin approvals</h2>
              <ul>
                {flagsData.pending_approvals.map((p) => (
                  <li key={p.id}>
                    <code>{p.flag.name}</code> → <strong>{String(p.requested_value)}</strong>{' '}
                    (requested at {p.requested_at ?? '—'})
                    <Button
                      variant="primary"
                      onClick={() => approve(p.id)}
                      disabled={approveMutation.isPending}
                      data-testid={`approve-${p.flag}`}
                    >
                      Approve
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <table className="feature-flag-table" data-testid="feature-flag-table">
            <thead>
              <tr>
                <th scope="col">Flag</th>
                <th scope="col">Stage</th>
                <th scope="col">Sensitive</th>
                <th scope="col">Current value</th>
                <th scope="col">Toggle</th>
              </tr>
            </thead>
            <tbody>
              {flagsData.flags.map((f) => (
                <tr key={f.name} data-testid={`row-${f.name}`}>
                  <td>
                    <code>{f.name}</code>
                    <div className="feature-flag-table__desc">{f.description}</div>
                  </td>
                  <td>{f.stage}</td>
                  <td>
                    {f.sensitive ? (
                      <span
                        className="feature-flag-table__badge feature-flag-table__badge--sensitive"
                        data-testid={`sensitive-${f.name}`}
                      >
                        Sensitive — requires 2nd approval
                      </span>
                    ) : (
                      <span className="feature-flag-table__badge">Standard</span>
                    )}
                  </td>
                  <td>{f.current_value ? 'true' : 'false'}</td>
                  <td>
                    <Button
                      variant="secondary"
                      onClick={() => openConfirm(f, !f.current_value)}
                      disabled={updateMutation.isPending}
                      data-testid={`toggle-${f.name}`}
                    >
                      Set to {String(!f.current_value)}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <ConfirmDialog
        isOpen={pending !== null}
        title={
          pending
            ? `${pending.flag.sensitive ? 'Sensitive — ' : ''}Flip ${pending.flag.name}`
            : ''
        }
        message={
          pending
            ? pending.flag.sensitive
              ? `This flag is SENSITIVE. Submitting will create a pending approval that a SECOND PLATFORM_ADMIN must approve before "${pending.flag.name}" becomes ${String(pending.newValue)}.`
              : `Set "${pending.flag.name}" to ${String(pending.newValue)} for this tenant?`
            : ''
        }
        confirmLabel={pending?.flag.sensitive ? 'Request approval' : 'Confirm'}
        cancelLabel="Cancel"
        variant={pending?.flag.sensitive ? 'warning' : 'info'}
        onClose={() => {
          setPending(null);
          setReason('');
          setReasonError(null);
        }}
        onConfirm={submitConfirm}
      >
        <label htmlFor="ff-reason">
          Reason (min 10 characters; written to the audit log)
        </label>
        <textarea
          id="ff-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          data-testid="ff-reason-input"
        />
        {reasonError && (
          <div role="alert" className="feature-flag-page__error">
            {reasonError}
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
}
