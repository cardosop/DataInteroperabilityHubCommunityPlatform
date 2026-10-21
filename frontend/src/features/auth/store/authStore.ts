/**
 * Auth Store (Zustand)
 * Global state management for authentication
 */

import { create } from 'zustand';
import { apiClient } from '../../../shared/api/client';
import { invalidateIdentityCaches } from '../../../shared/services/cacheIdentity';
import { useImpersonationStore } from '../../admin/impersonation/impersonationStore';
import { broadcastTenantSwitch } from '../crossTabTenantSwitch';
import type { LoginRequest, User } from '../../../shared/types/auth';
import { authService } from '../services/authService';

// ---------------------------------------------------------------------------
// W5.3 (R2-F4) — init generation counter.
//
// Every async continuation of initialize() checks its captured generation
// against this counter before mutating state. logout()/login() bump it the
// moment they start, and clearAuthState() bumps it when it fires — so a
// stale init loop (retry sleep, deferred /auth/me/, the zombie left behind
// when the safety timeout wins) can never re-authenticate a logged-out
// session or clobber a newer identity. This closes the race where
// initialize()'s 3s-retry loop kept running across a logout and
// re-applied the user AFTER the logout completed.
// ---------------------------------------------------------------------------
let initGeneration = 0;

/** An error that marks the session as unrecoverable (auth-dead). */
function isAuthDeadError(err: unknown): boolean {
  if (typeof err !== 'object' || err === null) return false;
  const anyErr = err as {
    response?: { status?: number };
    error?: { http_status?: number };
    authSessionUnrecoverable?: boolean;
  };
  if (anyErr.authSessionUnrecoverable === true) return true;
  if (anyErr.response?.status === 401) return true;
  return anyErr.error?.http_status === 401;
}

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
  // W5.3 (R2-F3) — the phantom `accessToken` field was REMOVED. It was
  // initialized to null and never written (the token lives in apiClient
  // module memory), yet three consumers read it: useActiveTenantId (the
  // SSE gate — always null, the stream never opened), SessionCountdownBanner
  // (always "unauthenticated"), and DatabricksSso tests. All now read the
  // real sources.
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
  isAuthenticated: getInitialIsAuthenticated(),
  isLoading: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    // A fresh login cancels any in-flight initialize retry loop — its
    // stale responses must never clobber the new identity.
    initGeneration += 1;
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
      apiClient._suppressAuthRedirect = false;
      // W5.2 (R2-F2) — a fresh identity: the previous session's cached
      // query data + capabilities must never render for this user.
      invalidateIdentityCaches('login');
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
    // Cancel any in-flight initialize retry loop — the session is
    // ending; a deferred /auth/me/ success must never re-authenticate
    // after this point (W5.3 late-init-no-reauth).
    initGeneration += 1;
    set({ isLoading: true });
    try {
      await authService.logout();
    } catch (error) {
      console.warn('Logout error:', error);
    } finally {
      try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
      // W5.1 (R2-F1) — logout must never leak the impersonation
      // capability into the next session: the bearer + metadata clear
      // through the store's single atomic clearSession.
      try {
        useImpersonationStore.getState().clearSession();
      } catch { /* ignore — impersonation module unavailable */ }
      set({
        user: null,
        active_tenant_id: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
      apiClient.setTenantIdGetter(null);
      // W5.2 (R2-F2) — the identity ended: drain every identity-scoped
      // cache (query data + capabilities) BEFORE the next render.
      invalidateIdentityCaches('logout');
    }
  },

  initialize: async () => {
    // W5.3 (R2-F4) — this run's generation. Every async continuation
    // below checks `isCurrent()` before mutating state; a newer
    // initialize()/login()/logout()/clearAuthState() bumps the counter
    // and cancels this run at the next checkpoint.
    const gen = ++initGeneration;
    const isCurrent = (): boolean => gen === initGeneration;

    // Phase P.7 — mark the store loading until /auth/me/ resolves so
    // ProtectedRoute renders a spinner instead of bouncing to /login
    // while a stale access token is being refreshed.  Without this, the
    // first navigation after a cold start (stored token revoked/expired)
    // raced the refresh and redirected authenticated users to /login
    // (measured 2026-08-28 in the ml-model-lifecycle E2E).
    set({ isLoading: true });
    const seqAtStart = authService.getUserWriteSeq();
    const INIT_MAX_MS = 60_000; // Safety: never hang > 60s; backend down/proxy issues can block indefinitely
    const safetyTimeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Auth initialization timeout')), INIT_MAX_MS)
    );

    const fetchUserWithRetry = async (): Promise<void> => {
      // Use direct fetch() instead of apiClient.get() to bypass the 401
      // interceptor.  The apiClient's _handleRefreshAndRetry does a hard
      // window.location.href = '/login' on refresh failure, which races
      // ahead of tryFetchUser's graceful clearAuthState() → LandingPage.
      // This matches the pattern in authService.refreshAccessToken() which
      // already uses direct fetch for the same reason.
      const token = apiClient.getAccessToken();
      const baseURL = apiClient.getClient().defaults.baseURL || '/api/v1';
      const response = await fetch(`${baseURL}/auth/me/`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        signal: AbortSignal.timeout(45_000),
      });
      // A newer identity transition happened while this request was in
      // flight (logout, fresh login, or a second initialize) — discard.
      if (!isCurrent()) return;
      if (!response.ok) {
        const error = new Error(`/auth/me/ returned ${response.status}`) as Error & { response?: { status: number } };
        error.response = { status: response.status };
        throw error;
      }
      const freshUser = await response.json() as User;
      if (!isCurrent()) return;
      // Clobber guard: this fetch started BEFORE any newer user write.
      // If a profile PATCH (or any setUser) landed while the request was
      // in flight, the store already holds NEWER state — applying this
      // pre-write response would revert the edit (JOURNEY-AUTH-PROFILE
      // intermittent header staleness under batch load, 2026-10-03).
      if (authService.getUserWriteSeq() === seqAtStart) {
        authService.setUser(freshUser);
        set({
          user: freshUser,
          isAuthenticated: true,
          isLoading: false,
        });
      } else {
        set({ isAuthenticated: true, isLoading: false });
      }
      syncTenantIdGetter(get);
      // Auth succeeded — enable the 401 interceptor's hard redirect.
      // Authenticated users whose session becomes unrecoverable should
      // be sent to /login.
      apiClient._suppressAuthRedirect = false;
    };

    const clearAuthState = () => {
      // W5.3 (R2-F4) — bump the generation FIRST: this is the terminal
      // auth-failed state, and it cancels every still-running
      // continuation of the init flow that invoked it (including the
      // zombie left behind when the safety timeout wins the race).
      initGeneration += 1;
      authService.clearAuth();
      // Auth failed — suppress the 401 interceptor's hard redirect.
      // The store's isAuthenticated=false will cause RootRoute at / to
      // show LandingPage; in-flight API 401 responses arriving after this
      // point must not trigger window.location.href = '/login'.
      apiClient._suppressAuthRedirect = true;
      apiClient.setTenantIdGetter(null);
      try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
      set({
        user: null,
        active_tenant_id: null,
        isAuthenticated: false,
        isLoading: false,
      });
      // W5.2 (R2-F2) — the identity ended through the failure path:
      // same drain as logout (the boundary must hold on EVERY way out).
      invalidateIdentityCaches('auth-failed');
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
          // W5.3 (R2-F4) — a stale init's 401 must not clearAuthState()
          // over a newer identity (e.g. a second initialize already
          // succeeded): only the CURRENT run may declare auth dead.
          if (!isCurrent()) return false;
          clearAuthState();
          return false;
        }
        if (retriesLeft > 0) {
          await new Promise((r) => setTimeout(r, 3000));
          // The retry sleep is the race window: a logout/login/new
          // initialize that happened during it cancels this loop.
          if (!isCurrent()) return false;
          return tryFetchUser(retriesLeft - 1);
        }
        // Fail-open on timeout/network: keep user from storage instead of redirecting to login.
        // E2E/CI load can congest backend; tokens may still be valid.
        const storedUser = authService.getUser();
        if (storedUser) {
          if (!isCurrent()) return false;
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
            if (!isCurrent()) return;
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
            if (!isCurrent()) return;
            refreshed = true;
          } catch (refreshErr) {
            const status = (refreshErr as { response?: { status?: number } })?.response?.status;
            const isRetryable = status === 429 || status === 503 || !status; // 429, 503, or network error
            if (isRetryable && attempt < 2) {
              await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
              if (!isCurrent()) return;
              continue;
            }
            // Permanent failure (401 invalid token, etc.) — clear auth and show login
            if (!isCurrent()) return;
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
          if (!isCurrent()) return;
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      } else {
        if (!isCurrent()) return;
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    };

    // Note: _suppressAuthRedirect is NOT scoped here — it is managed by
    // clearAuthState() (sets true) and successful auth paths (set false).
    // Tying it to auth state instead of initialize() scope ensures in-flight
    // API responses arriving after clearAuthState() don't trigger the 401
    // interceptor's window.location.href = '/login'.
    try {
      await Promise.race([runInit(), safetyTimeout]);
    } catch (error) {
      if (error instanceof Error && error.message === 'Auth initialization timeout') {
        // clearAuthState bumps the generation, so the still-running
        // runInit (a zombie after this race) aborts at its next
        // checkpoint instead of applying its result later.
        clearAuthState();
      } else if (isCurrent()) {
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
    if (userOverride) {
      // Local merge — no network, no failure modes.
      const current = get().user;
      const merged = { ...current, ...userOverride } as Partial<User>;
      const user = {
        ...merged,
        is_active: merged.is_active ?? current?.is_active ?? true,
      } as User;
      authService.setUser(user);
      if (user.feature_tenant_switch_enabled === false) {
        try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
        set({ user, active_tenant_id: null });
      } else {
        set({ user });
      }
      syncTenantIdGetter(get);
      return;
    }

    // W5.3 (R2-F4) — non-destructive refresh. The pre-fix catch treated
    // EVERY failure as session death: a transient network error or a
    // 5xx cleared the user and fired the auth-failed boundary — users
    // were logged out by backend hiccups. Only an auth-dead failure
    // (401 after the refresh also failed) is destructive; network/5xx
    // failures retry once, then keep the current state.
    const MAX_ATTEMPTS = 2;
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
      try {
        const seqAtStart = authService.getUserWriteSeq();
        const user = await authService.fetchUser();
        // Clobber guard — a newer user write (e.g. profile PATCH) landed
        // while this fetch was in flight; keep the newer store state
        // instead of reverting to the pre-write response.
        if (authService.getUserWriteSeq() !== seqAtStart) return;
        authService.setUser(user);
        if (user.feature_tenant_switch_enabled === false) {
          // The persisted override must die with the capability: a stale
          // localStorage value would leak into a fresh tab via
          // getInitialActiveTenantId and into useActiveTenantId's
          // cross-tab adoption (W5.3).
          try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
          set({ user, active_tenant_id: null });
        } else {
          set({ user });
        }
        syncTenantIdGetter(get);
        return;
      } catch (err) {
        if (isAuthDeadError(err)) {
          if (!get().isAuthenticated) {
            // Already logged out — nothing to clear (pre-W5.3 parity).
            return;
          }
          // Session unrecoverable — the pre-W5.3 destructive contract
          // (preserved): clear and fire the auth-failed boundary. Also
          // cancel any in-flight initialize loop.
          initGeneration += 1;
          authService.clearAuth();
          apiClient._suppressAuthRedirect = true;
          apiClient.setTenantIdGetter(null);
          try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
          set({
            user: null,
            active_tenant_id: null,
            isAuthenticated: false,
          });
          // W5.2 (R2-F2) — identity end through the refresh-failure path.
          invalidateIdentityCaches('auth-failed');
          return;
        }
        if (attempt < MAX_ATTEMPTS - 1) {
          // One bounded retry for the transient class.
          await new Promise((r) => setTimeout(r, 500));
          continue;
        }
        // Persistent transient failure — keep the current state; a
        // backend hiccup must never log the user out.
        console.warn('refreshUser failed after retry; keeping current state:', err);
        return;
      }
    }
  },

  clearError: () => {
    set({ error: null });
  },

  setActiveTenant: (tenant_id) => {
    const previous = get().active_tenant_id;
    try {
      if (tenant_id) {
        localStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, tenant_id);
      } else {
        localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY);
      }
    } catch { /* ignore storage errors */ }
    set({ active_tenant_id: tenant_id });
    syncTenantIdGetter(get);
    // W5.2 (R2-F2) — a REAL tenant change drains the tenant-scoped
    // query cache (query keys are not tenant-scoped); setting the same
    // tenant again is not a boundary (e.g. the initial hydration path).
    if (tenant_id !== previous) {
      invalidateIdentityCaches('tenant-switch');
      // W5.3 (R2-F3) — notify sibling tabs so their useActiveTenantId
      // (and the SSE stream it gates) re-derives. The pre-fix tree
      // exported broadcastTenantSwitch but NEVER called it — the
      // cross-tab tenant-switch contract was dead.
      broadcastTenantSwitch();
    }
  },

  clearActiveTenant: () => {
    const previous = get().active_tenant_id;
    try { localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY); } catch { /* ignore */ }
    set({ active_tenant_id: null });
    syncTenantIdGetter(get);
    // W5.2 (R2-F2) — falling back to the user's own tenant IS a tenant
    // change (and therefore a boundary) only when an override was active.
    if (previous) {
      invalidateIdentityCaches('tenant-switch');
    }
  },
}));
