/**
 * Auth Service Tests
 * Tests for auth service using real apiClient (no mocks of apiClient)
 *
 * Note: We mock axios at the module level to avoid real HTTP calls,
 * but we use the real apiClient instance, ensuring the service correctly
 * uses apiClient.getClient() and the actual service methods.
 */

import type { AxiosInstance } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
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

// Mock axios at module level - this allows apiClient to use real methods
// but intercepts HTTP calls for testing
vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

import axios from 'axios';
import { apiClient } from '../../../shared/api/client';
import { authService } from './authService';

// Get the mock instance from axios.create
const mockAxiosCreate = vi.mocked(axios.create);

describe('authService', () => {
  let mockAxiosInstance: AxiosInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
    localStorageMock.setItem.mockClear();
    localStorageMock.removeItem.mockClear();
    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    // Use the real client's methods, but we'll mock them via axios.create mock
    mockAxiosInstance = realClient;
    // Clear mock call history but keep implementations
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.post).mockClear();
    vi.mocked(mockAxiosInstance.delete).mockClear();
  });

  describe('login', () => {
    it('should reject when login fails with network error', async () => {
      vi.mocked(mockAxiosInstance.post).mockRejectedValue(new Error('Network error'));

      await expect(
        authService.login({ email: 'test@example.com', password: 'wrong' })
      ).rejects.toThrow('Network error');
      expect(localStorageMock.setItem).not.toHaveBeenCalledWith('access_token', expect.any(String));
    });

    it('should reject when login returns 401', async () => {
      const err: any = new Error('Unauthorized');
      err.response = { status: 401, data: { error: 'Invalid credentials' } };
      vi.mocked(mockAxiosInstance.post).mockRejectedValue(err);

      await expect(
        authService.login({ email: 'test@example.com', password: 'wrong' })
      ).rejects.toThrow();
    });

    it('should login and store tokens', async () => {
      const loginRequest: LoginRequest = {
        email: 'test@example.com',
        password: 'password123',
      };

      const mockLoginResponse: LoginResponse = {
        access_token: 'access-token-123',
        refresh_token: 'refresh-token-456',
      };

      const mockUser: User = {
        id: 'user-1',
        email: 'test@example.com',
        name: 'Test User',
        tenant_id: 'tenant-1',
        roles: ['USER'],
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValueOnce({
        data: mockLoginResponse,
      } as any);

      vi.mocked(mockAxiosInstance.get).mockResolvedValueOnce({
        data: mockUser,
      } as any);

      const result = await authService.login(loginRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('/auth/login/', loginRequest);
      expect(result.access_token).toBe('access-token-123');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'access-token-123');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refresh_token', 'refresh-token-456');
    });
  });

  describe('register', () => {
    it('should register a new user', async () => {
      vi.clearAllMocks(); // Clear any previous mocks

      const registerRequest: RegisterRequest = {
        email: 'newuser@example.com',
        password: 'password123',
        name: 'New User',
      };

      const mockRegisterResponse: RegisterResponse = {
        id: 'user-new',
        email: 'newuser@example.com',
        name: 'New User',
        tenant_id: 'tenant-1',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValueOnce({
        data: mockRegisterResponse,
      } as any);

      const result = await authService.register(registerRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        '/auth/register/',
        registerRequest
      );
      expect(result.id).toBe('user-new');
      expect(result.email).toBe('newuser@example.com');
    });
  });

  describe('requestPasswordReset', () => {
    it('should request password reset', async () => {
      vi.clearAllMocks();

      const resetRequest: PasswordResetRequest = {
        email: 'user@example.com',
      };

      const mockResponse: MessageResponse = {
        message: 'Password reset email sent',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValueOnce({
        data: mockResponse,
      } as any);

      const result = await authService.requestPasswordReset(resetRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        '/auth/password-reset/',
        resetRequest
      );
      expect(result.message).toBe('Password reset email sent');
    });
  });

  describe('confirmPasswordReset', () => {
    it('should confirm password reset', async () => {
      vi.clearAllMocks();

      const confirmRequest: PasswordResetConfirmRequest = {
        token: 'reset-token-123',
        new_password: 'newpassword123',
      };

      const mockResponse: MessageResponse = {
        message: 'Password reset successful',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValueOnce({
        data: mockResponse,
      } as any);

      const result = await authService.confirmPasswordReset(confirmRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        '/auth/password-reset/confirm/',
        confirmRequest
      );
      expect(result.message).toBe('Password reset successful');
    });
  });

  describe('logout', () => {
    it('should logout and clear auth data', async () => {
      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        status: 200,
      } as any);

      await authService.logout();

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('/auth/logout/');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should clear auth data even if logout endpoint fails', async () => {
      vi.mocked(mockAxiosInstance.post).mockRejectedValue(new Error('Network error'));

      await authService.logout();

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user');
    });
  });

  describe('refreshAccessToken', () => {
    it('should refresh access token', async () => {
      localStorageMock.getItem.mockReturnValue('refresh-token-456');

      const mockRefreshResponse: RefreshTokenResponse = {
        access_token: 'new-access-token-789',
        refresh_token: 'new-refresh-token-012',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockRefreshResponse,
      } as any);

      const result = await authService.refreshAccessToken();

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('/auth/refresh/', {
        refresh_token: 'refresh-token-456',
      } as RefreshTokenRequest);
      expect(result).toBe('new-access-token-789');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'new-access-token-789');
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'refresh_token',
        'new-refresh-token-012'
      );
    });

    it('should throw error if no refresh token', async () => {
      localStorageMock.getItem.mockReturnValue(null);

      await expect(authService.refreshAccessToken()).rejects.toThrow('No refresh token available');
    });
  });

  describe('fetchUser', () => {
    it('should fetch current user', async () => {
      const mockUser: User = {
        id: 'user-1',
        email: 'test@example.com',
        name: 'Test User',
        tenant_id: 'tenant-1',
        roles: ['USER'],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockUser,
      } as any);

      const result = await authService.fetchUser();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('/auth/me/');
      expect(result.id).toBe('user-1');
      expect(result.email).toBe('test@example.com');
    });
  });

  describe('fetchAndStoreUser', () => {
    it('should fetch and store user', async () => {
      const mockUser: User = {
        id: 'user-1',
        email: 'test@example.com',
        name: 'Test User',
        tenant_id: 'tenant-1',
        roles: ['USER'],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockUser,
      } as any);

      const result = await authService.fetchAndStoreUser();

      expect(localStorageMock.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockUser));
      expect(result.id).toBe('user-1');
    });
  });

  describe('listSessions', () => {
    it('should list active sessions', async () => {
      const mockSessions: Session[] = [
        {
          id: 'session-1',
          user_id: 'user-1',
          created_at: '2024-01-01T00:00:00Z',
          last_used_at: '2024-01-02T00:00:00Z',
          ip_address: '192.168.1.1',
          user_agent: 'Mozilla/5.0',
        },
        {
          id: 'session-2',
          user_id: 'user-1',
          created_at: '2024-01-01T00:00:00Z',
          last_used_at: '2024-01-02T00:00:00Z',
          ip_address: '192.168.1.2',
          user_agent: 'Mozilla/5.0',
        },
      ];

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockSessions,
      } as any);

      const result = await authService.listSessions();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('/auth/sessions/');
      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('session-1');
    });
  });

  describe('revokeSession', () => {
    it('should revoke a session', async () => {
      const mockResponse: MessageResponse = {
        message: 'Session revoked',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockResponse,
      } as any);

      const result = await authService.revokeSession('session-1');

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        '/auth/sessions/session-1/revoke/'
      );
      expect(result.message).toBe('Session revoked');
    });
  });

  describe('listAuthApiKeys', () => {
    it('should list auth API keys with pagination', async () => {
      const mockResponse = {
        count: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'key-1',
            name: 'API Key 1',
            created_at: '2024-01-01T00:00:00Z',
          },
          {
            id: 'key-2',
            name: 'API Key 2',
            created_at: '2024-01-02T00:00:00Z',
          },
        ] as AuthAPIKey[],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockResponse,
      } as any);

      const result = await authService.listAuthApiKeys({ page: 1, page_size: 20 });

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        '/auth/api-keys/?page=1&page_size=20'
      );
      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
    });

    it('should list auth API keys without pagination', async () => {
      const mockResponse = {
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        next: null,
        previous: null,
        results: [] as AuthAPIKey[],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockResponse,
      } as any);

      const result = await authService.listAuthApiKeys();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('/auth/api-keys/');
      expect(result.count).toBe(0);
    });
  });

  describe('createAuthApiKey', () => {
    it('should create an auth API key', async () => {
      const createRequest: AuthAPIKeyCreate = {
        name: 'New API Key',
      };

      const mockResponse: AuthAPIKeyCreateResponse = {
        id: 'key-new',
        name: 'New API Key',
        key: 'plaintext-key-123', // Only shown once
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockResponse,
      } as any);

      const result = await authService.createAuthApiKey(createRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        '/auth/api-keys/',
        createRequest
      );
      expect(result.id).toBe('key-new');
      expect(result.key).toBe('plaintext-key-123');
    });
  });

  describe('deleteAuthApiKey', () => {
    it('should delete an auth API key', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      await authService.deleteAuthApiKey('key-1');

      expect(vi.mocked(mockAxiosInstance.delete)).toHaveBeenCalledWith('/auth/api-keys/key-1/');
    });
  });

  describe('acceptInvitation', () => {
    it('should accept invitation and store tokens', async () => {
      const acceptRequest: AcceptInvitationRequest = {
        token: 'invitation-token-123',
        password: 'newpassword123',
      };

      const mockResponse: AcceptInvitationResponse = {
        access_token: 'access-token-123',
        refresh_token: 'refresh-token-456',
        user: {
          id: 'user-new',
          email: 'newuser@example.com',
          name: 'New User',
          tenant_id: 'tenant-1',
          roles: ['USER'],
        },
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockResponse,
      } as any);

      const result = await authService.acceptInvitation(acceptRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        '/auth/accept-invitation/',
        acceptRequest
      );
      expect(result.access_token).toBe('access-token-123');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'access-token-123');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refresh_token', 'refresh-token-456');
    });
  });

  describe('token management', () => {
    it('should get and set access token', () => {
      localStorageMock.getItem.mockReturnValue('test-token');
      const token = authService.getAccessToken();
      expect(token).toBe('test-token');

      authService.setAccessToken('new-token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'new-token');
    });

    it('should get and set refresh token', () => {
      localStorageMock.getItem.mockReturnValue('test-refresh-token');
      const token = authService.getRefreshToken();
      expect(token).toBe('test-refresh-token');

      authService.setRefreshToken('new-refresh-token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refresh_token', 'new-refresh-token');
    });
  });

  describe('user management', () => {
    it('should get and set user', () => {
      const mockUser: User = {
        id: 'user-1',
        email: 'test@example.com',
        name: 'Test User',
        tenant_id: 'tenant-1',
        roles: ['USER'],
      };

      localStorageMock.getItem.mockReturnValue(JSON.stringify(mockUser));
      const user = authService.getUser();
      expect(user?.id).toBe('user-1');

      authService.setUser(mockUser);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockUser));
    });

    it('should return null if user not in storage', () => {
      localStorageMock.getItem.mockReturnValue(null);
      const user = authService.getUser();
      expect(user).toBeNull();
    });

    it('should return null if user JSON is invalid', () => {
      localStorageMock.getItem.mockReturnValue('invalid-json');
      const user = authService.getUser();
      expect(user).toBeNull();
    });
  });

  describe('clearAuth', () => {
    it('should clear all auth data', () => {
      authService.clearAuth();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user');
    });
  });

  describe('isAuthenticated', () => {
    it('should return true if user is authenticated', () => {
      localStorageMock.getItem
        .mockReturnValueOnce('access-token-123')
        .mockReturnValueOnce(JSON.stringify({ id: 'user-1', email: 'test@example.com' }));
      expect(authService.isAuthenticated()).toBe(true);
    });

    it('should return false if no access token', () => {
      localStorageMock.getItem.mockReturnValue(null);
      expect(authService.isAuthenticated()).toBe(false);
    });

    it('should return false if no user', () => {
      localStorageMock.getItem.mockReturnValueOnce('access-token-123').mockReturnValueOnce(null);
      expect(authService.isAuthenticated()).toBe(false);
    });
  });
});
