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
  RefreshTokenRequest,
  RefreshTokenResponse,
  RegisterRequest,
  RegisterResponse,
  Session,
  User,
} from '../../../shared/types/auth';

const TOKEN_STORAGE_KEY = 'access_token';
const REFRESH_TOKEN_STORAGE_KEY = 'refresh_token';
const USER_STORAGE_KEY = 'user';

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
      if (response.data.refresh_token) {
        this.setRefreshToken(response.data.refresh_token);
      }
      apiClient._cookieAuthMode = false;
    } else {
      // Cookie mode: tokens are in httpOnly cookies, not in JS-accessible body.
      // Don't store anything in memory or localStorage.
      apiClient._cookieAuthMode = true;
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
    try {
      // Call logout endpoint if available
      await apiClient.getClient().post('/auth/logout/');
    } catch (error) {
      // Ignore errors on logout; only log outside tests to avoid stderr noise
      if (import.meta.env.MODE !== 'test') {
        console.warn('Logout endpoint error:', error);
      }
    } finally {
      this.clearAuth();
    }
  }

  async refreshAccessToken(): Promise<string> {
    // In cookie mode, refresh_token is in httpOnly cookie (sent automatically).
    // In legacy mode, we need the refresh_token from localStorage.
    if (!apiClient._cookieAuthMode) {
      const refreshToken = this.getRefreshToken();
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }
    }

    // Use fetch directly (bypass apiClient interceptors) to avoid the 401 interceptor
    // triggering a recursive refresh or hard redirect to /login during proactive refresh.
    const baseURL = apiClient.getClient().defaults.baseURL || '/api/v1';
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    try {
      // In cookie mode, refresh_token cookie is sent via credentials: 'include'.
      const body = apiClient._cookieAuthMode
        ? undefined
        : JSON.stringify({ refresh_token: this.getRefreshToken() } as RefreshTokenRequest);

      const fetchResponse = await fetch(`${baseURL}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        credentials: 'include',
        signal: controller.signal,
      });

      if (!fetchResponse.ok) {
        throw new Error(`Refresh failed with status ${fetchResponse.status}`);
      }

      const data = (await fetchResponse.json()) as RefreshTokenResponse;

      // In cookie mode, tokens are in httpOnly cookies — body may be empty.
      if (data.access_token) {
        this.setAccessToken(data.access_token);
      }
      if (data.refresh_token) {
        this.setRefreshToken(data.refresh_token);
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
    return response.data;
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
      if (response.data.refresh_token) {
        this.setRefreshToken(response.data.refresh_token);
      }
    }
    return response.data;
  }

  // Token management — Phase 11.1: access_token kept in JS module memory only
  getAccessToken(): string | null {
    return apiClient.getAccessToken();
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  }

  setAccessToken(token: string): void {
    // Phase 11.1: store only in apiClient memory, never in localStorage
    apiClient.setAccessToken(token);
  }

  setRefreshToken(token: string): void {
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
    apiClient.setRefreshToken(token);
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
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    // Tenant ID getter is managed by authStore (active_tenant_id || user.tenant_id)
  }

  // Clear all auth data
  clearAuth(): void {
    // Remove from localStorage (refresh_token, user, and legacy access_token if present)
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    // G4.4 (glittery-herding-graham): also clear active_tenant_id so direct
    // callers of clearAuth() don't leave stale tenant context.
    try { localStorage.removeItem('active_tenant_id'); } catch { /* ignore */ }
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
    return (!!this.getAccessToken() || !!this.getRefreshToken()) && !!this.getUser();
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
        const payload = JSON.parse(atob(storedToken.split('.')[1]));
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

    const refreshToken = this.getRefreshToken();
    if (refreshToken) {
      apiClient.setRefreshToken(refreshToken);
    }

    // Phase 220.4: detect cookie-based auth mode on page reload.
    // If we have a stored user profile but NO tokens in JS-accessible storage,
    // the session is carried by httpOnly cookies. Set cookie mode so that
    // isAuthenticated() returns true and API calls don't send Bearer headers.
    const hasUser = !!localStorage.getItem(USER_STORAGE_KEY);
    const hasAnyToken = !!storedToken || !!refreshToken;
    if (hasUser && !hasAnyToken) {
      apiClient._cookieAuthMode = true;
    }

    // Tenant ID getter is set by authStore.initialize after user is loaded
  }
}

export const authService = new AuthService();
