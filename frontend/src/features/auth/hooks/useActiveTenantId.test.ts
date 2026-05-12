/**
 * Phase 276.B.002 — useActiveTenantId hook test.
 *
 * Verifies the hook reads tenant_id from the JWT claim and reacts
 * to auth store changes.
 */
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useActiveTenantId, broadcastTenantSwitch } from './useActiveTenantId';

// Mock the auth store with a settable accessToken.
const mockGetState = vi.fn();
const mockSubscribe = vi.fn(() => vi.fn());

vi.mock('../store/authStore', () => ({
  useAuthStore: {
    getState: () => mockGetState(),
    subscribe: (cb: () => void) => mockSubscribe(cb),
  },
}));

function setToken(tenantId: string | null) {
  if (tenantId) {
    const payload = btoa(JSON.stringify({ tenant_id: tenantId, exp: 9999999999 }));
    mockGetState.mockReturnValue({ accessToken: `header.${payload}.sig` });
  } else {
    mockGetState.mockReturnValue({ accessToken: null });
  }
}

describe('useActiveTenantId', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns tenant_id from JWT claim', () => {
    setToken('tenant-abc-123');
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('tenant-abc-123');
  });

  it('returns null when no access token', () => {
    setToken(null);
    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBeNull();
  });

  it('reacts to auth store changes via subscribe', () => {
    setToken('initial-tenant');
    let subscriber: (() => void) | null = null;
    mockSubscribe.mockImplementation((cb: () => void) => {
      subscriber = cb;
      return vi.fn();
    });

    const { result } = renderHook(() => useActiveTenantId());
    expect(result.current).toBe('initial-tenant');

    // Simulate auth store change.
    act(() => {
      setToken('switched-tenant');
      subscriber?.();
    });

    expect(result.current).toBe('switched-tenant');
  });

  it('broadcastTenantSwitch writes to localStorage', () => {
    broadcastTenantSwitch();
    const stored = localStorage.getItem('auth:tenant-switch');
    expect(stored).toBeTruthy();
  });
});
