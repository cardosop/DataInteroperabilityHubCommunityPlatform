/**
 * Phase 277.B.017 — Multi-tab session sync hook.
 *
 * Listens for auth-related storage events so that:
 * - Logout in tab A revokes tab B (redirects to /login)
 * - Tenant switch in tab A propagates to tab B
 *
 * Uses the existing `broadcastTenantSwitch()` from 276.B.002
 * for tenant switches, and adds a `broadcastLogout()` for logout.
 */
import { useEffect } from 'react';

const LOGOUT_EVENT_KEY = 'auth:logout';

/** Broadcast a logout event to all other tabs. */
export function broadcastLogout(): void {
  try {
    localStorage.setItem(LOGOUT_EVENT_KEY, Date.now().toString());
    localStorage.removeItem('auth:tenant-switch');
  } catch {
    // localStorage may be unavailable in private browsing.
  }
}

/**
 * Hook: when another tab logs out or switches tenant, react.
 * @param onLogout — callback invoked when another tab logs out.
 * @param onTenantSwitch — callback invoked when another tab switches tenant.
 */
export function useMultiTabSync(
  onLogout: () => void,
  onTenantSwitch?: () => void,
): void {
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === LOGOUT_EVENT_KEY) {
        onLogout();
      }
      if (e.key === 'auth:tenant-switch' && onTenantSwitch) {
        onTenantSwitch();
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, [onLogout, onTenantSwitch]);
}
