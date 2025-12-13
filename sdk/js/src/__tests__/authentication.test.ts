/**
 * Authentication Tests
 * 
 * Tests for API key, JWT, token refresh, and error handling.
 */

import { DataHubClient } from '../client';
import { UnauthorizedError, ForbiddenError } from '../errors';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Authentication', () => {
  let client: DataHubClient;
  const mockAxiosInstance = {
    request: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
  });

  describe('API Key Authentication', () => {
    it('should set API token in Authorization header', () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'test-api-key',
      });

      const requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} };
      requestInterceptor(config);

      expect((config.headers as any).Authorization).toBe('Bearer test-api-key');
    });

    it('should allow setting token after initialization', () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
      });

      client.setApiToken('new-api-key');

      const requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} };
      requestInterceptor(config);

      expect((config.headers as any).Authorization).toBe('Bearer new-api-key');
    });

    it('should work without token if not provided', () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
      });

      const requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} };
      requestInterceptor(config);

      expect((config.headers as any).Authorization).toBeUndefined();
    });
  });

  describe('JWT Token Authentication', () => {
    it('should accept JWT token as API token', () => {
      const jwtToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';
      
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: jwtToken,
      });

      const requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} };
      requestInterceptor(config);

      expect((config.headers as any).Authorization).toBe(`Bearer ${jwtToken}`);
    });
  });

  describe('Token Refresh', () => {
    it('should refresh token on 401 error', async () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'expired-token',
      });

      const refreshCallback = jest.fn().mockResolvedValue('new-token');
      client.setTokenRefreshCallback(refreshCallback);

      // First request fails with 401
      const error401 = {
        response: {
          status: 401,
          data: {
            error: {
              code: 'AUTH_UNAUTHORIZED',
              message: 'Token expired',
              http_status: 401,
            },
          },
        },
        config: {
          method: 'GET',
          url: '/test',
          headers: {},
        },
      };

      // Second request succeeds after refresh
      const successResponse = {
        data: { success: true },
        status: 200,
      };

      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Mock the retry after refresh
      mockAxiosInstance.request
        .mockRejectedValueOnce(error401)
        .mockResolvedValueOnce(successResponse);

      // Simulate the interceptor behavior
      try {
        await responseInterceptor(error401);
      } catch (error) {
        // Expected to retry
      }

      expect(refreshCallback).toHaveBeenCalled();
    });

    it('should throw UnauthorizedError if token refresh fails', async () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'expired-token',
      });

      const refreshCallback = jest.fn().mockRejectedValue(new Error('Refresh failed'));
      client.setTokenRefreshCallback(refreshCallback);

      const error401 = {
        response: {
          status: 401,
          data: {
            error: {
              code: 'AUTH_UNAUTHORIZED',
              message: 'Token expired',
              http_status: 401,
            },
          },
        },
        config: {
          method: 'GET',
          url: '/test',
          headers: {},
        },
      };

      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];

      await expect(responseInterceptor(error401)).rejects.toThrow(UnauthorizedError);
      expect(refreshCallback).toHaveBeenCalled();
    });

    it('should not refresh token if callback not set', async () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'expired-token',
      });

      const error401 = {
        response: {
          status: 401,
          data: {
            error: {
              code: 'AUTH_UNAUTHORIZED',
              message: 'Token expired',
              http_status: 401,
            },
          },
        },
        config: {
          method: 'GET',
          url: '/test',
          headers: {},
        },
      };

      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];

      await expect(responseInterceptor(error401)).rejects.toThrow(UnauthorizedError);
    });
  });

  describe('Authentication Error Handling', () => {
    it('should throw UnauthorizedError for 401 responses', async () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'invalid-token',
      });

      const errorResponse = {
        response: {
          status: 401,
          data: {
            error: {
              code: 'AUTH_UNAUTHORIZED',
              message: 'Invalid credentials',
              http_status: 401,
              request_id: 'req-123',
            },
          },
        },
        config: {},
        request: {},
      };

      // Get the response interceptor
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Test the interceptor directly
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error).toBeInstanceOf(UnauthorizedError);
      }
    });

    it('should throw ForbiddenError for 403 responses', async () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'valid-token',
      });

      const errorResponse = {
        response: {
          status: 403,
          data: {
            error: {
              code: 'AUTH_FORBIDDEN',
              message: 'Permission denied',
              http_status: 403,
              request_id: 'req-123',
            },
          },
        },
        config: {},
        request: {},
      };

      // Get the response interceptor
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Test the interceptor directly
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error).toBeInstanceOf(ForbiddenError);
      }
    });

    it('should include request ID in error', async () => {
      client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'invalid-token',
      });

      const errorResponse = {
        response: {
          status: 401,
          data: {
            error: {
              code: 'AUTH_UNAUTHORIZED',
              message: 'Invalid credentials',
              http_status: 401,
              request_id: 'req-456',
            },
          },
        },
        config: {},
        request: {},
      };

      // Get the response interceptor
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error).toBeInstanceOf(UnauthorizedError);
        expect(error.requestId).toBe('req-456');
      }
    });
  });
});

