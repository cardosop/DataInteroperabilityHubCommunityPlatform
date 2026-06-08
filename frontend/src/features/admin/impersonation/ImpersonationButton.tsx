/**
 * Phase 235.4 — Impersonation start button (mount in UserEditPage).
 *
 * Visibility contract (235.4.14):
 *
 * 1. The component is rendered ONLY when the current authenticated
 *    user carries the PLATFORM_ADMIN role.
 * 2. Within the PLATFORM_ADMIN render path, the button is HIDDEN
 *    when the target user's tenant has ``impersonation_allowed=false``
 *    (defence-in-depth — the backend gate returns 403, but hiding
 *    the button avoids the wasteful round-trip + confused operator).
 * 3. Self-impersonation is hidden too — an operator clicking the
 *    button on their own user-detail page would be a no-op (the
 *    backend would reject because PLATFORM_ADMIN cannot be a target).
 */

import { useState } from 'react';

import { useAuthStore } from '../../auth/store/authStore';
import { useAdminImpersonateStart } from '../hooks/useAdmin';
import { useImpersonationStore } from './impersonationStore';

interface Props {
  /** Target user UUID. */
  targetUserId: string;
  /** Target tenant ID — required for the impersonation start request. */
  targetTenantId: string;
  /** Target tenant — used to enforce the ``impersonation_allowed`` gate. */
  targetTenantImpersonationAllowed?: boolean;
  /** Default duration cap (per-tenant) so we pre-fill the dialog. */
  targetTenantDefaultMaxMinutes?: number;
  /** Optional: hide on self-impersonation. */
  targetUserIsPlatformAdmin?: boolean;
}

export function ImpersonationButton({
  targetUserId,
  targetTenantId,
  targetTenantImpersonationAllowed,
  targetTenantDefaultMaxMinutes,
  targetUserIsPlatformAdmin,
}: Props) {
  const currentUser = useAuthStore((s) => s.user);
  const startSession = useImpersonationStore((s) => s.startSession);
  const startMutation = useAdminImpersonateStart();

  const [showDialog, setShowDialog] = useState(false);
  const [reason, setReason] = useState('');
  const [maxMinutes, setMaxMinutes] = useState<number>(
    targetTenantDefaultMaxMinutes ?? 60,
  );

  // Visibility gates.
  const isPlatformAdmin = currentUser?.roles?.includes('PLATFORM_ADMIN') ?? false;
  if (!isPlatformAdmin) return null;
  if (currentUser?.id === targetUserId) return null;
  if (targetTenantImpersonationAllowed === false) return null;
  if (targetUserIsPlatformAdmin === true) return null;

  const handleStart = () => {
    if (reason.trim().length < 10) {
      // The serializer rejects < 10 chars; surface inline rather
      // than letting the round-trip return 400.
      return;
    }
    startMutation.mutate(
      {
        tenantId: targetTenantId,
        userId: targetUserId,
      },
      {
        onSuccess: (data) => {
          // ``startSession`` is the single ATOMIC entry point that
          // persists the impersonation Bearer in apiClient AND the
          // session metadata in localStorage AND the in-memory
          // banner state — all three writes must complete before
          // the SPA navigates, or a fresh request would race the
          // new identity. See ``impersonationStore.startSession``.
          startSession(
            data,
            data.access_token,
            currentUser?.email ?? '(unknown)',
          );
          // Force a full reload so React Query re-fetches every
          // page-level query under the new identity. The
          // localStorage-persisted Bearer is picked up by the
          // apiClient constructor on the new page load.
          window.location.assign('/');
        },
      },
    );
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setShowDialog(true)}
        data-testid="impersonation-start-button"
        style={{
          backgroundColor: 'var(--color-error-700)',
          color: 'white',
          border: 'none',
          padding: '8px 14px',
          fontWeight: 600,
          borderRadius: '4px',
          cursor: 'pointer',
        }}
      >
        🛡 Impersonate user
      </button>
      {showDialog && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="impersonate-dialog-title"
          data-testid="impersonation-dialog"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000,
          }}
        >
          <div
            style={{
              backgroundColor: 'white',
              padding: '24px',
              borderRadius: '8px',
              width: '480px',
              maxWidth: '90vw',
            }}
          >
            <h2 id="impersonate-dialog-title" style={{ marginTop: 0 }}>
              Start impersonation session
            </h2>
            <p style={{ color: 'var(--color-text-secondary)' }}>
              You are about to assume this user&apos;s identity. All actions
              you take will be tagged with both your operator identity AND
              the user&apos;s identity in the audit log.
            </p>
            <label htmlFor="impersonation-reason" style={{ display: 'block', marginBottom: 4 }}>
              Reason (minimum 10 characters):
            </label>
            <textarea
              id="impersonation-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              style={{ width: '100%', boxSizing: 'border-box' }}
              data-testid="impersonation-reason-input"
            />
            <label htmlFor="impersonation-minutes" style={{ display: 'block', marginTop: 12, marginBottom: 4 }}>
              Max duration (minutes, 5–240):
            </label>
            <input
              id="impersonation-minutes"
              type="number"
              min={5}
              max={240}
              value={maxMinutes}
              onChange={(e) => setMaxMinutes(Number(e.target.value))}
              data-testid="impersonation-minutes-input"
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: 16 }}>
              <button
                type="button"
                onClick={() => setShowDialog(false)}
                disabled={startMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStart}
                disabled={startMutation.isPending || reason.trim().length < 10}
                style={{
                  backgroundColor: 'var(--color-error-700)',
                  color: 'white',
                  border: 'none',
                  padding: '8px 14px',
                  fontWeight: 600,
                  borderRadius: '4px',
                  cursor:
                    startMutation.isPending || reason.trim().length < 10
                      ? 'not-allowed'
                      : 'pointer',
                }}
                data-testid="impersonation-start-confirm"
              >
                {startMutation.isPending ? 'Starting…' : 'Start session'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
