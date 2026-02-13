/**
 * Auth Store (Zustand)
 * Global state management for authentication
 */

import { create } from 'zustand';
import { apiClient } from '../../../shared/api/client';
import type { LoginRequest, User } from '../../../shared/types/auth';
import { authService } from '../services/authService';

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

// Hydrate state from localStorage (used by initialize(), not at module load).
// Lazy: avoids touching localStorage when the store module is first loaded (e.g. in vitest workers).
function getInitialAuthStateFromStorage(): Pick<
  AuthState,
  'user' | 'isAuthenticated' | 'isLoading'
> {
  const token = authService.getAccessToken();
  const user = authService.getUser();

  if (token && user) {
    authService.initializeAuth();
    return {
      user: user ?? null,
      isAuthenticated: true,
      isLoading: false,
    };
  }

  return {
    user: null,
    isAuthenticated: false,
    isLoading: false,
  };
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
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
    // If already authenticated from initial state, verify token is still valid
    const currentState = get();
    if (currentState.isAuthenticated && currentState.user) {
      set({ isLoading: true });
      try {
        // Verify token is still valid by fetching user
        const freshUser = await authService.fetchUser();
        // Set tenant ID getter for API client
        if (freshUser?.tenant_id) {
          apiClient.setTenantIdGetter(() => freshUser.tenant_id);
        }
        set({
          user: freshUser,
          isAuthenticated: true,
          isLoading: false,
        });
      } catch (error) {
        // Token invalid, clear auth
        authService.clearAuth();
        apiClient.setTenantIdGetter(null);
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    } else {
      // Not authenticated, try to initialize from storage
      set({ isLoading: true });
      try {
        authService.initializeAuth();

        if (authService.isAuthenticated()) {
          const user = authService.getUser();
          if (user) {
            // Verify token is still valid by fetching user
            try {
              const freshUser = await authService.fetchUser();
              // Set tenant ID getter for API client
              if (freshUser?.tenant_id) {
                apiClient.setTenantIdGetter(() => freshUser.tenant_id);
              }
              set({
                user: freshUser,
                isAuthenticated: true,
                isLoading: false,
              });
            } catch (error) {
              // Token invalid, clear auth
              authService.clearAuth();
              apiClient.setTenantIdGetter(null);
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
