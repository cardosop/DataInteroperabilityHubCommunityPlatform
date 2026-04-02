/**
 * Auth Store (Zustand)
 * Global state management for authentication
 */

import { create } from 'zustand';
import { apiClient } from '../../../shared/api/client';
import type { LoginRequest, User } from '../../../shared/types/auth';
import { authService } from '../services/authService';

/** When a prior session exists in storage, start with isLoading: true so ProtectedRoute shows Loading instead of redirecting to login before initialize() runs. */
function getInitialIsLoading(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    // Phase 11.1: access_token is no longer stored in localStorage.
    // Check for user profile only — its presence indicates a prior session that
    // may be resumable via refresh_token cookie or in-memory token.
    return !!localStorage.getItem('user');
  } catch {
    return false;
  }
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
  user: null,
  active_tenant_id: getInitialActiveTenantId(),
  isAuthenticated: false,
  isLoading: getInitialIsLoading(),
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
        set({ isLoading: true });
        await tryFetchUser(2);
        return;
      }

      set({ isLoading: true });
      authService.initializeAuth();

      // Phase 11.1: after page reload, access_token is lost (in-memory only).
      // If we have a refresh_token but no access_token, proactively refresh
      // to obtain a new access_token BEFORE calling /auth/me/. Retry on
      // transient failures (429 rate-limit, network errors) which are common
      // under E2E parallel load where multiple browser tabs hit /auth/refresh/
      // simultaneously after page reloads.
      if (!authService.getAccessToken() && authService.getRefreshToken()) {
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
