/**
 * Authentication Service
 * Handles login, logout, token refresh, and user management
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  AcceptInvitationRequest,
  AcceptInvitationResponse,
  AuthAPIKey,
  AuthAPIKeyCreate,
  AuthAPIKeyCreateResponse,
  LoginRequest,
  LoginResponse,
  MessageResponse,
  PasswordResetConfirmRequest,
  PasswordResetRequest,
  ProfileUpdateRequest,
  RefreshTokenResponse,
  RegisterRequest,
  RegisterResponse,
  Session,
  User,
} from '../../../shared/types/auth';

const TOKEN_STORAGE_KEY = 'access_token';
const USER_STORAGE_KEY = 'user';
// Phase 220.4 — persists the auth-mode of the LAST login response
// ('cookie' when the backend keeps tokens in httpOnly cookies, 'body'
// when the body carries access_token). initializeAuth() restores the
// mode from this marker on full page reloads — storage presence is NOT
// a reliable discriminator anymore (11.1 leaves no stored token after
// a body-mode login by design).
const AUTH_MODE_KEY = 'auth_mode';

// Monotonic write sequence: bumped by every setUser. Async fetch paths
// (authStore.initialize's direct /auth/me/ fetch, refreshUser's fetch)
// capture the sequence BEFORE the request and skip their apply when a
// newer write (e.g. a profile PATCH) landed while the request was in
// flight — otherwise a slow pre-PATCH response clobbers the edited
// name in the store (E2E JOURNEY-AUTH-PROFILE intermittent header
// staleness, 2026-10-03).
let _userWriteSeq = 0;

class AuthService {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient
      .getClient()
      .post<LoginResponse>('/auth/login/', credentials, { timeout: 45000 });

    // Phase 220.4: detect cookie-based auth mode.
    // When USE_HTTPONLY_AUTH_COOKIES=True on the backend, the response body
    // does NOT contain access_token (tokens are in httpOnly cookies instead).
    if (response.data.access_token) {
      // Legacy mode: store tokens in memory / localStorage
      this.setAccessToken(response.data.access_token);
      apiClient._cookieAuthMode = false;
    } else {
      // Cookie mode: tokens are in httpOnly cookies, not in JS-accessible body.
      // Don't store anything in memory or localStorage.
      apiClient._cookieAuthMode = true;
    }
    // Persist the mode so a full page reload restores the SAME mode —
    // see AUTH_MODE_KEY + initializeAuth()'s restore logic.
    try {
      localStorage.setItem(AUTH_MODE_KEY, apiClient._cookieAuthMode ? 'cookie' : 'body');
    } catch {
      // localStorage unavailable — the reload heuristic falls back to the legacy shape
    }

    // Fetch and store user info. If this fails, roll back tokens to prevent
    // zombie state where tokens exist but user profile is null (C1 — glittery-herding-graham).
    try {
      await this.fetchAndStoreUser();
    } catch (err) {
      this.clearAuth();
      throw err;
    }

    return response.data;
  }

  async register(payload: RegisterRequest): Promise<RegisterResponse> {
    const response = await apiClient
      .getClient()
      .post<RegisterResponse>('/auth/register/', payload, { timeout: 45000 });
    return response.data;
  }

  async requestPasswordReset(payload: PasswordResetRequest): Promise<MessageResponse> {
    const response = await apiClient
      .getClient()
      .post<MessageResponse>('/auth/password-reset/', payload);
    return response.data;
  }

  async confirmPasswordReset(payload: PasswordResetConfirmRequest): Promise<MessageResponse> {
    const response = await apiClient
      .getClient()
      .post<MessageResponse>('/auth/password-reset/confirm/', payload);
    return response.data;
  }

  async verifyEmail(token: string): Promise<MessageResponse> {
    const response = await apiClient
      .getClient()
      .post<MessageResponse>('/auth/verify-email/', { token }, { timeout: 45000 });
    return response.data;
  }

  async resendVerificationEmail(email: string): Promise<MessageResponse> {
    const response = await apiClient
      .getClient()
      .post<MessageResponse>('/auth/resend-verification/', { email }, { timeout: 45000 });
    return response.data;
  }

  async logout(): Promise<void> {
    // Clear auth state immediately — the user is logged out locally
    // regardless of whether the server-side POST succeeds.  This also
    // fixes E2E flake where the POST can take >15s under backend load
    // and the test's waitForFunction times out before the finally block.
    this.clearAuth();
    try {
      await apiClient.getClient().post('/auth/logout/', undefined, { timeout: 5000 });
    } catch (error) {
      // Ignore errors on logout; only log outside tests to avoid stderr noise
      if (import.meta.env.MODE !== 'test') {
        console.warn('Logout endpoint error:', error);
      }
    }
  }

  async refreshAccessToken(): Promise<string> {
    // Use fetch directly (bypass apiClient interceptors) to avoid the 401 interceptor
    // triggering a recursive refresh or hard redirect to /login during proactive refresh.
    const baseURL = apiClient.getClient().defaults.baseURL || '/api/v1';
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    try {
      const fetchResponse = await fetch(`${baseURL}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        signal: controller.signal,
      });

      if (!fetchResponse.ok) {
        const error = new Error(`Refresh failed with status ${fetchResponse.status}`) as Error & {
          response?: { status: number };
        };
        error.response = { status: fetchResponse.status };
        throw error;
      }

      const data = (await fetchResponse.json()) as RefreshTokenResponse;

      // In cookie mode, tokens are in httpOnly cookies — body may be empty.
      if (data.access_token) {
        this.setAccessToken(data.access_token);
      }

      return data.access_token || '';
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async fetchUser(): Promise<User> {
    // 45s timeout: E2E/CI load can congest backend; auth store retries and fail-open handle transient failures
    const response = await apiClient.getClient().get<User>('/auth/me/', { timeout: 45000 });
    return response.data;
  }

  /** PATCH /auth/me/ — update profile (display_name, avatar, preferences) */
  async updateProfile(payload: ProfileUpdateRequest): Promise<User> {
    const body: Record<string, unknown> = {};
    if (payload.display_name !== undefined) body.display_name = payload.display_name;
    if (payload.avatar !== undefined) body.avatar = payload.avatar;
    if (payload.preferences !== undefined) body.preferences = payload.preferences;
    // Phase 278.R.6 (close-test-coverage-gaps 3.2) — product-tour
    // cross-device persistence. The type declared this field but the
    // body builder dropped it, so ProductTourGate's PATCH always sent
    // an empty payload and the backend never learned the tour was seen.
    if (payload.has_seen_tour !== undefined) body.has_seen_tour = payload.has_seen_tour;

    const response = await apiClient.getClient().patch<User>('/auth/me/', body);
    const user = response.data;
    this.setUser(user);
    return user;
  }

  async fetchAndStoreUser(): Promise<User> {
    const user = await this.fetchUser();
    this.setUser(user);
    return user;
  }

  /** List active sessions (refresh tokens) — GET /auth/sessions/ */
  async listSessions(): Promise<Session[]> {
    const response = await apiClient.getClient().get<Session[]>('/auth/sessions/');
    // Phase 1.5 — normalize at the service boundary: SessionListPage calls
    // ``sessions.map`` and a non-array 200 (proxy error envelope, drift)
    // used to crash the render with "sessions.map is not a function".
    return Array.isArray(response.data) ? response.data : [];
  }

  /** Revoke a session — POST /auth/sessions/{id}/revoke/ */
  async revokeSession(sessionId: string): Promise<MessageResponse> {
    const response = await apiClient
      .getClient()
      .post<MessageResponse>(`/auth/sessions/${sessionId}/revoke/`);
    return response.data;
  }

  /** List auth API keys (paginated) — GET /auth/api-keys/ */
  async listAuthApiKeys(params?: {
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<AuthAPIKey>> {
    const searchParams = new URLSearchParams();
    if (params?.page != null) searchParams.set('page', String(params.page));
    if (params?.page_size != null) searchParams.set('page_size', String(params.page_size));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<AuthAPIKey>>(`/auth/api-keys/${query}`);
    return response.data;
  }

  /** Create auth API key — POST /auth/api-keys/ (plaintext key in response, shown once) */
  async createAuthApiKey(payload: AuthAPIKeyCreate): Promise<AuthAPIKeyCreateResponse> {
    const response = await apiClient
      .getClient()
      .post<AuthAPIKeyCreateResponse>('/auth/api-keys/', payload);
    return response.data;
  }

  /** Delete auth API key — DELETE /auth/api-keys/{id}/ */
  async deleteAuthApiKey(id: string): Promise<void> {
    await apiClient.getClient().delete(`/auth/api-keys/${id}/`);
  }

  /** Accept invitation — POST /auth/accept-invitation/ (sets password, returns tokens) */
  async acceptInvitation(payload: AcceptInvitationRequest): Promise<AcceptInvitationResponse> {
    const response = await apiClient
      .getClient()
      .post<AcceptInvitationResponse>('/auth/accept-invitation/', payload);
    if (response.data.access_token) {
      this.setAccessToken(response.data.access_token);
    }
    return response.data;
  }

  // Token management — Phase 11.1: access_token kept in JS module memory only
  getAccessToken(): string | null {
    return apiClient.getAccessToken();
  }

  setAccessToken(token: string): void {
    // Phase 11.1: store in apiClient memory (primary) — localStorage
    // must NEVER retain the access_token after a UI login (XSS surface).
    // Phase 277.B.067: cross-tab sync piggybacks on the `storage` event
    // instead — write the token so sibling tabs receive an access_token
    // event carrying the value as the EVENT PAYLOAD (e.newValue), then
    // remove it in the same tick. The event fires on the setItem even
    // though the key is gone before the next paint, so login AND refresh
    // rotation propagate across tabs while the 11.1 hardening contract
    // (token absent from localStorage) holds.
    apiClient.setAccessToken(token);
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    } catch {
      // localStorage unavailable — cross-tab sync not possible
    }
  }

  // User management
  getUser(): User | null {
    const userStr = localStorage.getItem(USER_STORAGE_KEY);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr) as User;
    } catch {
      return null;
    }
  }

  setUser(user: User): void {
    _userWriteSeq += 1;
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    // Tenant ID getter is managed by authStore (active_tenant_id || user.tenant_id)
  }

  /** Monotonic counter for every user write (profile PATCH, fetches, login). */
  getUserWriteSeq(): number {
    return _userWriteSeq;
  }

  // Clear all auth data
  clearAuth(): void {
    // Remove from localStorage (user and legacy access_token if present).
    // Also clear legacy refresh_token key from older clients.
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem('refresh_token');
    localStorage.removeItem(USER_STORAGE_KEY);
    localStorage.removeItem(AUTH_MODE_KEY);
    // G4.4 (glittery-herding-graham): also clear active_tenant_id so direct
    // callers of clearAuth() don't leave stale tenant context.
    try {
      localStorage.removeItem('active_tenant_id');
    } catch {
      /* ignore */
    }
    // Phase 277.B.067 — bump sync timestamp so other tabs detect logout
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('_auth_sync_ts', String(Date.now()));
      }
    } catch {
      /* ignore */
    }
    apiClient.clearTokens();
  }

  // Check if user is authenticated
  isAuthenticated(): boolean {
    // Phase 11.1: access_token is in-memory only; also consider authenticated
    // if we have a user profile (session may be resumable via refresh_token cookie).
    // Phase 220.4: in cookie mode, tokens are in httpOnly cookies (not in JS),
    // so we consider authenticated if we have a stored user profile.
    if (apiClient._cookieAuthMode) {
      return !!this.getUser();
    }
    return !!this.getAccessToken() && !!this.getUser();
  }

  // Initialize auth state from storage
  initializeAuth(): void {
    // Phase 11.1: access_token is no longer written to localStorage by UI login
    // (it lives in JS module memory only). However, E2E tests inject access_token
    // into localStorage via loginViaApiAndInject for session restoration across
    // page reloads. Read it into memory if present — do NOT remove it, because
    // page.goto() in Playwright causes full page reloads that clear JS memory,
    // and the token needs to survive multiple reloads within the same test.
    // Security: UI login (authService.setAccessToken) never writes to localStorage,
    // so production users are unaffected.
    // C3 (glittery-herding-graham): clean up stale expired tokens before the
    // cookie-mode heuristic. An expired access_token from a prior body-mode
    // session makes hasAnyToken=true, preventing cookie mode detection.
    let storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (storedToken) {
      try {
        // JWT segments are base64url-encoded (RFC 7519): '-' instead of '+',
        // '_' instead of '/', no padding.  atob() requires standard base64.
        // Convert before decoding — without this, any base64url payload
        // containing '-' or '_' (e.g., UUIDs in the sub/jti/tenant_id claims)
        // throws InvalidCharacterError, the catch block removes the token
        // from localStorage, and the fallback cookie-mode path triggers
        // _cookieAuthMode → no Bearer header → 401 → redirect to /login.
        const base64 = storedToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        const payload = JSON.parse(atob(base64));
        if (payload.exp && payload.exp * 1000 < Date.now()) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          storedToken = null;
        }
      } catch {
        // Malformed token — remove it
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        storedToken = null;
      }
    }

    if (storedToken) {
      apiClient.setAccessToken(storedToken);
    }

    // Phase 220.4: restore the cookie-based auth mode on page reload from
    // the LAST-KNOWN login response shape — NOT from "no token in
    // storage". The old heuristic (hasUser && !hasAnyToken → cookie mode)
    // misfires on legacy deployments after the 11.1 hardening: a full
    // reload has user but no stored access_token BY DESIGN, the SPA then
    // flipped to cookie mode on a legacy backend, dropped the Bearer
    // header, and every call 401'd with AUTH_UNAUTHORIZED (measured:
    // AUD-004 non-existent-id rendered "Unauthorized" instead of the
    // 404 boundary). The login response is the reliable discriminator:
    // cookie-mode backends return no access_token in the body.
    const hasUser = !!localStorage.getItem(USER_STORAGE_KEY);
    const persistedMode = localStorage.getItem(AUTH_MODE_KEY);
    if (persistedMode === 'cookie' && hasUser) {
      apiClient._cookieAuthMode = true;
    } else if (persistedMode === 'body') {
      apiClient._cookieAuthMode = false;
    } else if (hasUser && !storedToken) {
      // Pre-marker sessions (no AUTH_MODE_KEY written yet): keep the old
      // heuristic so cookie-mode deployments that predate the marker
      // still boot correctly.
      apiClient._cookieAuthMode = true;
    }

    // Tenant ID getter is set by authStore.initialize after user is loaded
  }
}

export const authService = new AuthService();

// P.7 root fix — seed the in-memory access token SYNCHRONOUSLY at module
// load.  On a cold page load the store hydrates `user` from localStorage
// and the app shell mounts BEFORE initialize()'s first await; components
// that fire requests on mount (Header → GET /auth/me/tenants/) then sent
// a bearer-less request, got a 401, and the interceptor's refresh path
// (no httpOnly cookie in the E2E storageState) cleared the session and
// bounced authenticated users to /login (measured 2026-08-29 in the
// ml-model-lifecycle E2E).  Seeding here closes the race for every
// caller: the token is in the client before any component can render.
// The method is idempotent and SSR-safe (guards on typeof window).
authService.initializeAuth();
