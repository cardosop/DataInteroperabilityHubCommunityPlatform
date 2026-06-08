/**
 * Phase 235.4 — Red top-banner shown while the operator is impersonating.
 *
 * Mounting site: ``frontend/src/App.tsx`` (just above ``RouterProvider``)
 * so it sits at the top of every page including login/error routes —
 * an operator who somehow lands on /login during an impersonation
 * session still sees the banner.
 *
 * Dismissibility contract (235.4.13): the banner has NO close
 * button. The ONLY way to dismiss it is the Exit button, which calls
 * the exit endpoint and clears the local session state on success.
 */

import { useCallback } from 'react';

import { useAdminImpersonateExit } from '../hooks/useAdmin';
import { useImpersonationStore } from './impersonationStore';

export function ImpersonationBanner() {
  const session = useImpersonationStore((s) => s.session);
  const impersonatorEmail = useImpersonationStore((s) => s.impersonatorEmail);
  const clearSession = useImpersonationStore((s) => s.clearSession);
  const exitMutation = useAdminImpersonateExit();

  const handleExit = useCallback(() => {
    if (!session) return;
    exitMutation.mutate(
      undefined,
      {
        onSuccess: () => {
          clearSession();
          // Force a full reload to re-bootstrap auth as the
          // original PLATFORM_ADMIN. The exit endpoint already
          // invalidated the JWT server-side; the SPA needs a fresh
          // /auth/me/ to pick up the original identity.
          window.location.assign('/');
        },
      },
    );
  }, [session, exitMutation, clearSession]);

  if (!session) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="impersonation-banner"
      style={{
        backgroundColor: 'var(--color-error-700)',
        color: 'white',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '14px',
        fontWeight: 600,
        position: 'sticky',
        top: 0,
        zIndex: 1000,
      }}
    >
      <span>
        🛡 IMPERSONATING — operator{' '}
        <strong>{impersonatorEmail ?? '(unknown)'}</strong> is viewing this
        session as user{' '}
        <strong>{session.session.impersonated_user_id.slice(0, 8)}…</strong>. Session
        expires at {new Date(session.session.expires_at).toLocaleString()}.
      </span>
      <button
        type="button"
        onClick={handleExit}
        disabled={exitMutation.isPending}
        data-testid="impersonation-banner-exit"
        style={{
          backgroundColor: 'white',
          color: 'var(--color-error-700)',
          border: 'none',
          padding: '6px 14px',
          fontWeight: 700,
          borderRadius: '4px',
          cursor: exitMutation.isPending ? 'not-allowed' : 'pointer',
          marginLeft: '16px',
        }}
      >
        {exitMutation.isPending ? 'Ending…' : 'Exit'}
      </button>
    </div>
  );
}
