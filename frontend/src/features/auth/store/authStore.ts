/**
 * Auth Store (Zustand)
 * Global state management for authentication
 */

import { create } from 'zustand';
import { apiClient } from '../../../shared/api/client';
import type { LoginRequest, User } from '../../../shared/types/auth';
import { authService } from '../services/authService';

/** When tokens exist in storage, start with isLoading: true so ProtectedRoute shows Loading instead of redirecting to login before initialize() runs. */
function getInitialIsLoading(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return !!(localStorage.getItem('access_token') && localStorage.getItem('user'));
  } catch {
    return false;
  }
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: getInitialIsLoading(),
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      await authService.login(credentials);
      const user = authService.getUser();
      // Set tenant ID getter for API client
      if (user?.tenant_id) {
        apiClient.setTenantIdGetter(() => user.tenant_id);
      }
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
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
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  initialize: async () => {
    const fetchUserWithRetry = async (_retries = 1): Promise<void> => {
      const freshUser = await authService.fetchUser();
      if (freshUser?.tenant_id) {
        apiClient.setTenantIdGetter(() => freshUser.tenant_id);
      }
      set({
        user: freshUser,
        isAuthenticated: true,
        isLoading: false,
      });
    };

    const clearAuthState = () => {
      authService.clearAuth();
      apiClient.setTenantIdGetter(null);
      set({
        user: null,
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
          if (storedUser.tenant_id) {
            apiClient.setTenantIdGetter(() => storedUser.tenant_id);
          }
          set({
            user: storedUser,
            isAuthenticated: true,
            isLoading: false,
          });
          return true;
        }
        clearAuthState();
        return false;
      }
    };

    // If already authenticated from initial state, verify token is still valid
    const currentState = get();
    if (currentState.isAuthenticated && currentState.user) {
      set({ isLoading: true });
      await tryFetchUser(2);
      return;
    }

    // Not authenticated, try to initialize from storage
    set({ isLoading: true });
    try {
      authService.initializeAuth();

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
    } catch (error) {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Initialization failed',
      });
    }
  },

  refreshUser: async () => {
    try {
      const user = await authService.fetchAndStoreUser();
      // Set tenant ID getter for API client
      if (user?.tenant_id) {
        apiClient.setTenantIdGetter(() => user.tenant_id);
      }
      set({ user });
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
        isAuthenticated: false,
      });
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));
