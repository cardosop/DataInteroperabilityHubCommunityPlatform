/**
 * Phase 276.B.002 — useActiveTenantId hook.
 *
 * Centralized hook that returns the ACTIVE tenant with the request-path
 * precedence:
 *
 *   1. the cross-tab persisted override (storage event path — another
 *      tab switched tenant),
 *   2. `active_tenant_id` (this tab's tenant-switch override),
 *   3. `user.tenant_id` (the user store, /auth/me/),
 *   4. the JWT `tenant_id` claim of the REAL access token
 *      (apiClient module memory — the store has no token field).
 *
 * W5.3 (R2-F3) root fix: the pre-fix hook read
 * `useAuthStore.getState().accessToken` — a store field initialized to
 * null and NEVER written — so the hook always returned null and the
 * SSE stream never opened. The real token lives in apiClient; the user
 * store carries the tenant-switch override.
 *
 * Deliberately NOT impersonation-aware: the hook's consumer is the
 * notification SSE stream, which cannot attach the impersonation
 * bearer (EventSource sends no headers), so the stream must follow the
 * credentials that are actually sent — the operator's.
 */
import { useEffect, useState } from 'react';
import { apiClient } from '../../../shared/api/client';
import { TENANT_SWITCH_EVENT_KEY } from '../crossTabTenantSwitch';
import { useAuthStore } from '../store/authStore';

/** Re-decode the JWT claim on every call — always fresh. */
function readTenantIdFromToken(): string | null {
  try {
    const token = apiClient.getAccessToken();
    if (!token) return null;
    // JWT segments are base64url-encoded (RFC 7519): '-' instead of '+',
    // '_' instead of '/'. atob() requires standard base64 — decode
    // without the conversion and any payload containing '-'/'_' (UUIDs
    // in sub/tenant_id) throws InvalidCharacterError → silent null.
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    return payload.tenant_id || null;
  } catch {
    return null;
  }
}

/** Read the persisted override written by setActiveTenant (any tab). */
function readPersistedActiveTenantId(): string | null {
  try {
    return localStorage.getItem('active_tenant_id');
  } catch {
    return null;
  }
}

export function useActiveTenantId(): string | null {
  const activeTenantId = useAuthStore((s) => s.active_tenant_id);
  const userTenantId = useAuthStore((s) => s.user?.tenant_id ?? null);

  // The override adopted from ANOTHER tab's switch (via the storage
  // event). Cleared whenever THIS tab changes its own override — the
  // local action always wins over the external one.
  const [externalOverride, setExternalOverride] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === TENANT_SWITCH_EVENT_KEY) {
        setExternalOverride(readPersistedActiveTenantId());
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  useEffect(() => {
    setExternalOverride(null);
  }, [activeTenantId]);

  return externalOverride ?? activeTenantId ?? userTenantId ?? readTenantIdFromToken();
}
