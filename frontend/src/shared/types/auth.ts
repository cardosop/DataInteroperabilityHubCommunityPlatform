/**
 * Authentication Types
 */

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  tenant_id?: string | null;
}

export interface RegisterResponse {
  id: string;
  email: string;
  name: string;
  tenant_id: string | null;
  created_at: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
}

export interface User {
  id: string;
  email: string;
  name: string;
  roles: string[];
  tenant_id: string;
  tenant_name?: string;
  is_active: boolean;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

/** Active session (refresh token) from GET /auth/sessions/ */
export interface Session {
  id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  is_current: boolean;
}

/** Auth API key (list/retrieve) — login/programmatic, not BaaS */
export interface AuthAPIKey {
  id: string;
  name: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

/** Create auth API key request */
export interface AuthAPIKeyCreate {
  name: string;
  scopes?: string[];
  expires_in_days?: number | null;
}

/** Create auth API key response (plaintext key shown once) */
export interface AuthAPIKeyCreateResponse {
  id: string;
  name: string;
  api_key: string;
  scopes: string[];
  expires_at: string | null;
  created_at: string;
}

/** Accept invitation request */
export interface AcceptInvitationRequest {
  token: string;
  password: string;
}

/** Accept invitation response (same as login) */
export interface AcceptInvitationResponse {
  access_token: string;
  refresh_token?: string;
  token_type: 'Bearer';
  expires_in: number;
}
