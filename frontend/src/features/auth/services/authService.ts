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
    const response = await apiClient.getClient().post<LoginResponse>('/auth/login/', credentials);

    // Store tokens
    this.setAccessToken(response.data.access_token);
    this.setRefreshToken(response.data.refresh_token);

    // Fetch and store user info
    await this.fetchAndStoreUser();

    return response.data;
  }

  async register(payload: RegisterRequest): Promise<RegisterResponse> {
    const response = await apiClient.getClient().post<RegisterResponse>('/auth/register/', payload);
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

  async logout(): Promise<void> {
    try {
      // Call logout endpoint if available
      await apiClient.getClient().post('/auth/logout/');
    } catch (error) {
      // Ignore errors on logout
      console.warn('Logout endpoint error:', error);
    } finally {
      this.clearAuth();
    }
  }

  async refreshAccessToken(): Promise<string> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await apiClient.getClient().post<RefreshTokenResponse>('/auth/refresh/', {
      refresh_token: refreshToken,
    } as RefreshTokenRequest);

    this.setAccessToken(response.data.access_token);
    if (response.data.refresh_token) {
      this.setRefreshToken(response.data.refresh_token);
    }

    return response.data.access_token;
  }

  async fetchUser(): Promise<User> {
    const response = await apiClient.getClient().get<User>('/auth/me/');
    return response.data;
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

  // Token management
  getAccessToken(): string | null {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  }

  setAccessToken(token: string): void {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
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
    // Update tenant ID getter when user changes
    apiClient.setTenantIdGetter(() => user?.tenant_id);
  }

  // Clear all auth data
  clearAuth(): void {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    apiClient.clearTokens();
  }

  // Check if user is authenticated
  isAuthenticated(): boolean {
    return !!this.getAccessToken() && !!this.getUser();
  }

  // Initialize auth state from storage
  initializeAuth(): void {
    const token = this.getAccessToken();
    const refreshToken = this.getRefreshToken();

    if (token) {
      apiClient.setAccessToken(token);
    }
    if (refreshToken) {
      apiClient.setRefreshToken(refreshToken);
    }

    // Set tenant ID getter for API client
    apiClient.setTenantIdGetter(() => {
      const user = this.getUser();
      return user?.tenant_id;
    });
  }
}

export const authService = new AuthService();
