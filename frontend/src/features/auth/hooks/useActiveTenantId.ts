/**
 * Phase 276.B.002 — useActiveTenantId hook.
 *
 * Centralized hook that returns the current tenant_id from the JWT
 * claim in the access token. Reacts to `storage` events so a tenant
 * switch in one tab propagates to other tabs (multi-tab session sync).
 *
 * Replace ALL direct `user.tenant_id` reads with this hook.
 */
import { useCallback, useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';

/** Re-decode the JWT claim on every call — always fresh. */
function readTenantIdFromToken(): string | null {
  try {
    const token = useAuthStore.getState().accessToken;
    if (!token) return null;
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.tenant_id || null;
  } catch {
    return null;
  }
}

export function useActiveTenantId(): string | null {
  const [tenantId, setTenantId] = useState<string | null>(() =>
    readTenantIdFromToken(),
  );

  // Phase 276.B.002 — cross-tab sync via storage events.
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === 'auth:tenant-switch') {
        setTenantId(readTenantIdFromToken());
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  // Re-read token on auth store changes.
  const refresh = useCallback(() => {
    setTenantId(readTenantIdFromToken());
  }, []);

  // Subscribe to auth store changes (Zustand).
  useEffect(() => {
    const unsub = useAuthStore.subscribe(() => refresh());
    return unsub;
  }, [refresh]);

  return tenantId;
}

/**
 * Phase 276.B.002 — broadcast a tenant switch to other tabs.
 * Called AFTER switchTenant() completes successfully.
 */
export function broadcastTenantSwitch(): void {
  try {
    localStorage.setItem('auth:tenant-switch', Date.now().toString());
  } catch {
    // localStorage may be unavailable in private browsing.
  }
}
