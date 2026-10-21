/**
 * W5.3 (oss-release-remediation R2-F3) — useActiveTenantId pins.
 *
 * The hook must derive the active tenant from the REAL identity sources
 * with the request-path precedence:
 *
 *   1. cross-tab persisted override (storage event path)
 *   2. `active_tenant_id` (tenant-switch override, the real store action)
 *   3. `user.tenant_id` (the user store, /auth/me/)
 *   4. the JWT `tenant_id` claim (the real access token in apiClient)
 *
 * The pre-fix hook read `useAuthStore.getState().accessToken` — a store
 * field that was initialized to null and NEVER written anywhere, so the
 * hook always returned null and the SSE stream never opened. These pins
 * exercise the REAL store actions, the REAL apiClient token, and REAL
 * StorageEvents — no store mocks (the pre-fix suite mocked the store
 * into faking a token field that production never sets).
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { apiClient } from '../../../shared/api/client';
import {
  TENANT_SWITCH_EVENT_KEY,
  broadcastTenantSwitch,
} from '../crossTabTenantSwitch';
import { useAuthStore } from '../store/authStore';
import { useActiveTenantId } from './useActiveTenantId';

/** Base64url-encode a JWT payload segment (RFC 7519). */
function jwtPayloadSegment(payload: Record<string, unknown>): string {
  return btoa(JSON.stringify(payload)).replace(/\+/g, '-').replace(/\//g, '_');
}

function jwtWithTenant(tenantId: string): string {
  return `header.${jwtPayloadSegment({ tenant_id: tenantId, exp: 9999999999 })}.sig`;
}

function seededUser(tenantId: string) {
  return {
    id: 'u1',
    email: 'ta@example.com',
    name: 'Tenant Admin',
    roles: ['TENANT_ADMIN'],
    tenant_id: tenantId,
    is_active: true,
  };
}

const RESET_STATE = {
  user: null,
  active_tenant_id: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

describe('useActiveTenantId', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({ ...RESET_STATE });
    apiClient.clearTokens();
    apiClient.setTenantIdGetter(null);
  });

  afterEach(() => {
    localStorage.clear();
    useAuthStore.setState({ ...RESET_STATE });
    apiClient.clearTokens();
    apiClient.setTenantIdGetter(null);
  });

  it('returns the user store tenant_id when authenticated with no override', () => {
    useAuthStore.setState({
      user: seededUser('tenant-store-1'),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('tenant-store-1');
  });

  it('returns null when no identity source is available', () => {
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBeNull();
  });

  it('falls back to the JWT tenant_id claim when the user store is empty', () => {
    apiClient.setAccessToken(jwtWithTenant('tenant-jwt-1'));
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('tenant-jwt-1');
  });

  it('prefers the active_tenant_id override and reacts to the real setActiveTenant action', () => {
    useAuthStore.setState({
      user: seededUser('tenant-store-1'),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('tenant-store-1');

    act(() => {
      useAuthStore.getState().setActiveTenant('tenant-override-2');
    });
    expect(result.current).toBe('tenant-override-2');
  });

  it('falls back to the user tenant after the real clearActiveTenant action', () => {
    useAuthStore.setState({
      user: seededUser('tenant-store-1'),
      active_tenant_id: 'tenant-override-2',
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('tenant-override-2');

    act(() => {
      useAuthStore.getState().clearActiveTenant();
    });
    expect(result.current).toBe('tenant-store-1');
  });

  it('adopts the persisted override written by another tab (real StorageEvent)', () => {
    useAuthStore.setState({
      user: seededUser('tenant-store-1'),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('tenant-store-1');

    // Tab A's setActiveTenant persists the override, then broadcasts.
    localStorage.setItem('active_tenant_id', 'tenant-other-tab-9');
    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: TENANT_SWITCH_EVENT_KEY,
          newValue: String(Date.now()),
        }),
      );
    });
    expect(result.current).toBe('tenant-other-tab-9');
  });

  it('a local switch after a cross-tab event wins over the external override', () => {
    useAuthStore.setState({
      user: seededUser('tenant-store-1'),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useActiveTenantId());

    localStorage.setItem('active_tenant_id', 'tenant-other-tab-9');
    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: TENANT_SWITCH_EVENT_KEY,
          newValue: String(Date.now()),
        }),
      );
    });
    expect(result.current).toBe('tenant-other-tab-9');

    act(() => {
      useAuthStore.getState().setActiveTenant('tenant-local-3');
    });
    expect(result.current).toBe('tenant-local-3');
  });

  it('broadcastTenantSwitch writes the shared cross-tab key', () => {
    broadcastTenantSwitch();
    const stored = localStorage.getItem(TENANT_SWITCH_EVENT_KEY);
    expect(stored).toBeTruthy();
  });
});
