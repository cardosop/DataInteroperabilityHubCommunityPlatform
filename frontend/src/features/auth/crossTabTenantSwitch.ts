/**
 * W5.3 (oss-release-remediation R2-F3) — the cross-tab tenant-switch
 * contract, single-sourced.
 *
 * `authStore.setActiveTenant` persists the override and broadcasts via
 * this key; `useActiveTenantId` re-derives on the storage event in
 * sibling tabs; `TenantSyncBanner` shows the "Tenant changed in another
 * tab" prompt on the same key. The literal was previously triplicated
 * across three modules — a drift hazard.
 */

export const TENANT_SWITCH_EVENT_KEY = 'auth:tenant-switch';

/**
 * Broadcast a tenant switch to other tabs. Called by the auth store
 * AFTER the active tenant actually changes.
 */
export function broadcastTenantSwitch(): void {
  try {
    localStorage.setItem(TENANT_SWITCH_EVENT_KEY, Date.now().toString());
  } catch {
    // localStorage may be unavailable in private browsing.
  }
}
