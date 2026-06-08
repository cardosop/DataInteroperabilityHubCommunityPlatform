/**
 * Auth Store (Zustand)
 * Global state management for authentication
 */

import { create } from 'zustand';
import { apiClient } from '../../../shared/api/client';
import type { LoginRequest, User } from '../../../shared/types/auth';
import { authService } from '../services/authService';

// ---------------------------------------------------------------------------
// Phase 213.I — Synchronous hydration helpers.
//
// The auth store now hydrates `user`, `isAuthenticated`, and `isLoading`
// synchronously from localStorage on first render so that ProtectedRoute
// can make an immediate role-gate decision without waiting for /auth/me/.
// Previously, only `isLoading` was hydrated (to `true`), which caused a
// 2-retry × 3s + 60s safety-timeout blocking init before ProtectedRoute
// could redirect to /403 or render children — a real product UX bug on
// cold staging pods.
// ---------------------------------------------------------------------------

/** Synchronously read the stored user profile from localStorage. */
export function getInitialUser(): User | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

/**
 * Returns `true` when a stored user profile exists.
 *
 * Cookie-mode default stores refresh/access tokens in httpOnly cookies, so
 * localStorage no longer carries `refresh_token`.
 */
export function getInitialIsAuthenticated(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return !!localStorage.getItem('user');
  } catch {
    return false;
  }
}

/**
 * Phase 213.I.3 — always returns `false`.
 *
 * When the store can hydrate synchronously (user in storage), it is not
 * loading from the user's perspective — role-gate
 * decisions can be made immediately. When it cannot hydrate, the user
 * is unauthenticated and ProtectedRoute redirects to /login on first
 * render — there is also nothing to wait for.
 */
export function getInitialIsLoading(): boolean {
  return false;
}

const ACTIVE_TENANT_STORAGE_KEY = 'active_tenant_id';

/** Read persisted active tenant from localStorage at store startup. */
function getInitialActiveTenantId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(ACTIVE_TENANT_STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

interface AuthState {
  user: User | null;
  /** Active tenant for X-Tenant-Id header; when set, overrides user.tenant_id */
  active_tenant_id: string | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
  refreshUser: (userOverride?: Partial<User>) => Promise<void>;
  clearError: () => void;
  setActiveTenant: (tenant_id: string | null) => void;
  clearActiveTenant: () => void;
}

/** Sync X-Tenant-Id getter: when feature enabled, active_tenant_id || user.tenant_id; else null (backend rejects X-Tenant-Id when disabled). */
function syncTenantIdGetter(get: () => AuthState): void {
  apiClient.setTenantIdGetter(() => {
    const s = get();
    if (s.user?.feature_tenant_switch_enabled === false) {
      return null;
    }
    return s.active_tenant_id || s.user?.tenant_id || null;
  });
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Phase 213.I.4 — synchronous hydration from localStorage.
  user: getInitialUser(),
  active_tenant_id: getInitialActiveTenantId(),
  accessToken: null,
  isAuthenticated: getInitialIsAuthenticated(),
  isLoading: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      await authService.login(credentials);
      const user = authService.getUser();
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      syncTenantIdGetter(get);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed';
      set({
        isLoading: false,
        error: errorMessage,
        isAuthenticated: false,
        user: null,
      });
      throw error;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      await authService.logout();
    } catch (error) {
      console.warn('Logout error:', error);
    } finally {
      try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
      set({
        user: null,
        active_tenant_id: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
      apiClient.setTenantIdGetter(null);
    }
  },

  initialize: async () => {
    const INIT_MAX_MS = 60_000; // Safety: never hang > 60s; backend down/proxy issues can block indefinitely
    const safetyTimeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Auth initialization timeout')), INIT_MAX_MS)
    );

    const fetchUserWithRetry = async (): Promise<void> => {
      const freshUser = await authService.fetchUser();
      set({
        user: freshUser,
        isAuthenticated: true,
        isLoading: false,
      });
      syncTenantIdGetter(get);
    };

    const clearAuthState = () => {
      authService.clearAuth();
      apiClient.setTenantIdGetter(null);
      try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
      set({
        user: null,
        active_tenant_id: null,
        isAuthenticated: false,
        isLoading: false,
      });
    };

    const is401 = (err: unknown): boolean =>
      typeof err === 'object' &&
      err !== null &&
      'response' in err &&
      (err as { response?: { status?: number } }).response?.status === 401;

    const tryFetchUser = async (retriesLeft: number): Promise<boolean> => {
      try {
        await fetchUserWithRetry();
        return true;
      } catch (error) {
        if (is401(error)) {
          clearAuthState();
          return false;
        }
        if (retriesLeft > 0) {
          await new Promise((r) => setTimeout(r, 3000));
          return tryFetchUser(retriesLeft - 1);
        }
        // Fail-open on timeout/network: keep user from storage instead of redirecting to login.
        // E2E/CI load can congest backend; tokens may still be valid.
        const storedUser = authService.getUser();
        if (storedUser) {
          set({
            user: storedUser,
            isAuthenticated: true,
            isLoading: false,
          });
          syncTenantIdGetter(get);
          return true;
        }
        clearAuthState();
        return false;
      }
    };

    const runInit = async (): Promise<void> => {
      const currentState = get();
      if (currentState.isAuthenticated && currentState.user) {
        // Phase 213.I.5 — hydrated from localStorage; do NOT flip
        // isLoading. Run /auth/me/ as a background refresh. On 401
        // clearAuthState() fires → ProtectedRoute re-renders → redirect
        // to /login. On network/timeout failure, the stored user is
        // kept (fail-open at lines ~162-173).
        //
        // CRITICAL: initializeAuth() must run before any API call so cookie
        // mode is detected consistently on first paint.
        authService.initializeAuth();
        syncTenantIdGetter(get);

        // Proactively refresh the access token if it's missing (typical
        // after page reload — Phase 11.1 stores access_token in memory
        // only). This ensures the first API call from a component has a
        // valid token instead of relying on the 401-retry interceptor.
        if (!authService.getAccessToken()) {
          try {
            await authService.refreshAccessToken();
          } catch {
            // Refresh failed — tryFetchUser below will also fail with 401
            // and clearAuthState() will redirect to /login. No action needed.
          }
        }

        await tryFetchUser(2);
        return;
      }

      // Cold-start: no stored user. ProtectedRoute has already
      // redirected to /login on the first render (isAuthenticated is
      // false, isLoading is false), so this branch runs invisibly.
      authService.initializeAuth();

      // Phase 11.1: after page reload, access_token is lost (in-memory only).
      // Proactively refresh via httpOnly cookie BEFORE calling /auth/me/.
      // Retry on
      // transient failures (429 rate-limit, network errors) which are common
      // under E2E parallel load where multiple browser tabs hit /auth/refresh/
      // simultaneously after page reloads.
      if (!authService.getAccessToken()) {
        let refreshed = false;
        for (let attempt = 0; attempt < 3 && !refreshed; attempt++) {
          try {
            await authService.refreshAccessToken();
            refreshed = true;
          } catch (refreshErr) {
            const status = (refreshErr as { response?: { status?: number } })?.response?.status;
            const isRetryable = status === 429 || status === 503 || !status; // 429, 503, or network error
            if (isRetryable && attempt < 2) {
              await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
              continue;
            }
            // Permanent failure (401 invalid token, etc.) — clear auth and show login
            clearAuthState();
            return;
          }
        }
      }

      // Cookie mode can authenticate entirely via cookies even when no token
      // is visible in JS memory; attempt /auth/me/ unconditionally.
      const recovered = await tryFetchUser(2);
      if (recovered) {
        return;
      }

      if (authService.isAuthenticated()) {
        const user = authService.getUser();
        if (user) {
          await tryFetchUser(2);
        } else {
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      } else {
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    };

    try {
      await Promise.race([runInit(), safetyTimeout]);
    } catch (error) {
      if (error instanceof Error && error.message === 'Auth initialization timeout') {
        clearAuthState();
      } else {
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: error instanceof Error ? error.message : 'Initialization failed',
        });
      }
    }
  },

  refreshUser: async (userOverride?: Partial<User>) => {
    try {
      let user: User;
      if (userOverride) {
        const current = get().user;
        const merged = { ...current, ...userOverride } as Partial<User>;
        user = {
          ...merged,
          is_active: merged.is_active ?? current?.is_active ?? true,
        } as User;
      } else {
        user = await authService.fetchAndStoreUser();
      }
      authService.setUser(user);
      if (user.feature_tenant_switch_enabled === false) {
        set({ user, active_tenant_id: null });
      } else {
        set({ user });
      }
      syncTenantIdGetter(get);
    } catch (err) {
      console.error('Failed to refresh user:', err);
      // If refresh fails, user might be logged out
      const state = get();
      if (!state.isAuthenticated) {
        // Already logged out, ignore
        return;
      }
      // Try to clear and re-initialize
      authService.clearAuth();
      apiClient.setTenantIdGetter(null);
      set({
        user: null,
        active_tenant_id: null,
        isAuthenticated: false,
      });
    }
  },

  clearError: () => {
    set({ error: null });
  },

  setActiveTenant: (tenant_id) => {
    try {
      if (tenant_id) {
        localStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, tenant_id);
      } else {
        localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY);
      }
    } catch { /* ignore storage errors */ }
    set({ active_tenant_id: tenant_id });
    syncTenantIdGetter(get);
  },

  clearActiveTenant: () => {
    try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
    set({ active_tenant_id: null });
    syncTenantIdGetter(get);
  },
}));
