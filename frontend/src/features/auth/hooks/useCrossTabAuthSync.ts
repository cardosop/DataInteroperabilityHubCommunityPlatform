/**
 * Phase 277.B.067 — cross-tab auth token sync via ``storage`` event.
 *
 * When a user logs in or out in one browser tab, the ``localStorage``
 * for ``access_token`` changes.  The ``storage`` event fires in every
 * OTHER tab sharing the same origin, allowing those tabs to react:
 *
 * - **Login in another tab** → hydrate the new ``access_token`` into
 *   ``apiClient`` + trigger ``authService.initializeAuth()`` so the
 *   UI reflects the authenticated state immediately.
 * - **Logout in another tab** → clear ``apiClient`` in-memory tokens +
 *   redirect to ``/login``.
 *
 * This hook is a no-op outside the browser (SSR / test environments
 * where ``window`` or ``localStorage`` are unavailable).
 */

import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../../shared/api/client';
import { authService } from '../services/authService';

const ACCESS_TOKEN_KEY = 'access_token';
// Must match authService.USER_STORAGE_KEY ('user').
const USER_KEY = 'user';

/**
 * Write a ``_auth_sync_ts`` key to localStorage to force a ``storage``
 * event in sibling tabs even when the ``access_token`` value hasn't
 * changed (e.g. the token was rotated but the new value happens to be
 * identical — vanishingly rare, but we still want the timestamp bump).
 *
 * The event payload carries the timestamp so receivers can deduplicate.
 */
function _bumpSyncTimestamp(): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('_auth_sync_ts', String(Date.now()));
    }
  } catch {
    // localStorage unavailable — no cross-tab sync possible
  }
}

/** Clear the sync timestamp (called on logout). */
function _clearSyncTimestamp(): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('_auth_sync_ts');
    }
  } catch {
    // noop
  }
}

/**
 * Hook: listen for auth token changes from other tabs and sync state.
 *
 * Must be mounted once at the app root (e.g. ``App.tsx``).  It is
 * idempotent — mounting it twice produces two listeners, but the
 * dedup guard prevents double-initialization.
 */
export function useCrossTabAuthSync(): void {
  const navigate = useNavigate();
  const initializedRef = useRef(false);

  useEffect(() => {
    // Only run in browser environments
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    // Dedup guard: prevent double-initialization during React strict-mode
    // double-mount in development. The ref MUST be reset in the cleanup —
    // StrictMode's dev double-mount runs cleanup between the two effect
    // passes, so without the reset the second pass early-returns and the
    // storage listener is NEVER attached (the cross-tab E2E proved it:
    // tab B only un-authed via the slow server-side refresh revocation,
    // never via the storage event).
    if (initializedRef.current) return;
    initializedRef.current = true;

    function handleStorageEvent(event: StorageEvent): void {
      if (event.key === ACCESS_TOKEN_KEY) {
        // ── Login or token refresh in another tab ──────────────
        // Phase 11.1: the writer (authService.setAccessToken) REMOVES the
        // token from localStorage in the same tick it wrote it, so the
        // value can only come from the EVENT PAYLOAD (e.newValue), never
        // from a localStorage read. A removal event (newValue null) is
        // either that write's own cleanup or the first removal of a
        // logout — logout itself is driven by the user-key removal
        // below, so removal events are ignored here.
        const newAccessToken = event.newValue;
        if (!newAccessToken) {
          return;
        }
        // Validate the JWT hasn't expired before adopting it. A value
        // that is not a 3-segment JWT is REJECTED outright — previously a
        // wrong segment count fell through the guard and the malformed
        // value was adopted as an access token.
        const parts = newAccessToken.split('.');
        if (parts.length !== 3) {
          return;
        }
        try {
          const payload = JSON.parse(atob(parts[1]));
          if (payload.exp && payload.exp * 1000 <= Date.now()) {
            // Expired token — don't adopt; the other tab will
            // refresh it, which will fire another storage event.
            return;
          }
        } catch {
          // Malformed JWT — ignore
          return;
        }

        // Adopt the new token into apiClient memory and re-initialize
        // the auth store so the UI updates.
        apiClient.setAccessToken(newAccessToken);

        // Trigger auth re-initialization to refresh user, tenants, etc.
        try {
          authService.initializeAuth();
        } catch {
          // If initialization fails (e.g. token already expired by the
          // time we tried), clear and redirect.
          apiClient.clearTokens();
          navigate('/login', { replace: true });
        }
        return;
      }

      if (event.key === USER_KEY && event.newValue === null) {
        // ── Logout in another tab ─────────────────────────────
        // clearAuth() removes access_token first and the user profile
        // LAST — the user-key removal is the reliable "session ended"
        // signal (a plain access_token removal is ambiguous: the 11.1
        // sync write removes the token right after writing it).
        apiClient.clearTokens();
        _clearSyncTimestamp();
        navigate('/login', { replace: true });
      }
    }

    window.addEventListener('storage', handleStorageEvent);

    return () => {
      window.removeEventListener('storage', handleStorageEvent);
      initializedRef.current = false;
    };
  }, [navigate]);

  // Expose helpers on the module so login/logout flows can bump the
  // sync timestamp after mutating localStorage.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as Window & { __crossTabAuthSync?: { bump: () => void; clear: () => void } }).__crossTabAuthSync = {
        bump: _bumpSyncTimestamp,
        clear: _clearSyncTimestamp,
      };
    }
  }, []);
}
