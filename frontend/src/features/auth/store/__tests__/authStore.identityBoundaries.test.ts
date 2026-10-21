/**
 * W5.2 (oss-release-remediation R2-F2) — pins for the identity-boundary
 * invalidation firing from the auth store.
 *
 * The REAL cacheIdentity bus receives the boundaries (test listeners
 * register/unregister around each assertion — no bus mocks). logout
 * runs the REAL action against the REAL authService (offline → the
 * service call fails → the store's finally still clears state and fires
 * the boundary — the exact production failure path). Only authService
 * itself is module-mocked so the login success path is reachable
 * without a backend (infrastructure seam, the repo convention).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/authService', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../services/authService')>();
  // Override on the REAL instance (spreading would drop the class
  // prototype methods — getUserWriteSeq & co. must stay live).
  original.authService.login = vi.fn(async () => ({})) as never;
  original.authService.getUser = vi.fn(
    () =>
      ({
        id: 'u1',
        email: 'ta@example.com',
        tenant_id: 't1',
        roles: ['TENANT_ADMIN'],
      }) as never,
  );
  // Permanent 401 — the cold-start refresh fails fast into
  // clearAuthState (no 2s/4s retry sleeps, the 401 class is final).
  original.authService.refreshAccessToken = vi.fn(async () => {
    throw Object.assign(new Error('refresh rejected'), {
      response: { status: 401 },
    });
  }) as never;
  return original;
});

import { registerIdentityCacheInvalidator } from '../../../../shared/services/cacheIdentity';
import { useAuthStore } from '../authStore';

const RESET_STATE = {
  user: null,
  active_tenant_id: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

describe('authStore identity boundaries', () => {
  beforeEach(() => {
    useAuthStore.setState({ ...RESET_STATE });
  });

  afterEach(() => {
    useAuthStore.setState({ ...RESET_STATE });
    localStorage.clear();
  });

  it('logout fires the logout boundary through the real bus', async () => {
    useAuthStore.setState({
      user: { id: 'u1', email: 'ta@example.com', tenant_id: 't1', roles: [] },
      isAuthenticated: true,
    });
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    try {
      await useAuthStore.getState().logout();
      expect(seen).toEqual(['logout']);
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    } finally {
      unregister();
    }
  });

  it('login success fires the login boundary', async () => {
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    try {
      await useAuthStore.getState().login({ email: 'ta@example.com', password: 'pw' });
      expect(seen).toEqual(['login']);
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    } finally {
      unregister();
    }
  });

  it('setActiveTenant fires tenant-switch ONLY when the tenant changes', () => {
    useAuthStore.setState({ active_tenant_id: 't1' });
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    try {
      useAuthStore.getState().setActiveTenant('t2');
      expect(seen).toEqual(['tenant-switch']);
      useAuthStore.getState().setActiveTenant('t2'); // same tenant — no boundary
      expect(seen).toEqual(['tenant-switch']);
    } finally {
      unregister();
    }
  });

  it('clearActiveTenant fires tenant-switch only when a tenant was active', () => {
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    try {
      useAuthStore.getState().clearActiveTenant(); // none active — no boundary
      expect(seen).toEqual([]);
      useAuthStore.setState({ active_tenant_id: 't9' });
      useAuthStore.getState().clearActiveTenant();
      expect(seen).toEqual(['tenant-switch']);
    } finally {
      unregister();
    }
  });

  it('initialize auth failure (401) fires the auth-failed boundary', async () => {
    // Drive the real clearAuthState path: no stored user, /auth/me/ 401s.
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 })
    ) as unknown as typeof fetch;
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    try {
      await useAuthStore.getState().initialize();
      expect(seen).toContain('auth-failed');
    } finally {
      globalThis.fetch = originalFetch;
      unregister();
    }
  });

  it('a failed login does NOT fire any boundary', async () => {
    const { authService } = await import('../../services/authService');
    (authService.login as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('invalid credentials')
    );
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    try {
      await expect(
        useAuthStore.getState().login({ email: 'ta@example.com', password: 'bad' })
      ).rejects.toThrow('invalid credentials');
      expect(seen).toEqual([]);
    } finally {
      unregister();
    }
  });
});
