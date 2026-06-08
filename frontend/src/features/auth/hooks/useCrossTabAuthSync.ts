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
    // double-mount in development.
    if (initializedRef.current) return;
    initializedRef.current = true;

    function handleStorageEvent(event: StorageEvent): void {
      // Only react to auth-relevant keys
      if (event.key !== ACCESS_TOKEN_KEY && event.key !== '_auth_sync_ts') {
        return;
      }

      // Ignore events where the key was set to null (cleared) — handled
      // by the removeItem path below.
      const newAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY);

      if (newAccessToken) {
        // ── Login or token refresh in another tab ──────────────
        // Validate the JWT hasn't expired before adopting it.
        try {
          const parts = newAccessToken.split('.');
          if (parts.length === 3) {
            const payload = JSON.parse(atob(parts[1]));
            if (payload.exp && payload.exp * 1000 <= Date.now()) {
              // Expired token — don't adopt; the other tab will
              // refresh it, which will fire another storage event.
              return;
            }
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
      } else {
        // ── Logout in another tab ─────────────────────────────
        apiClient.clearTokens();
        _clearSyncTimestamp();
        navigate('/login', { replace: true });
      }
    }

    window.addEventListener('storage', handleStorageEvent);

    return () => {
      window.removeEventListener('storage', handleStorageEvent);
    };
  }, [navigate]);

  // Expose helpers on the module so login/logout flows can bump the
  // sync timestamp after mutating localStorage.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).__crossTabAuthSync = {
        bump: _bumpSyncTimestamp,
        clear: _clearSyncTimestamp,
      };
    }
  }, []);
}
