/**
 * API Client Tests
 * Tests for error shape normalization and tenant ID header
 */

import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ApiError } from '../types/api';

// Create mock instance that will be reused
let mockAxiosInstance: AxiosInstance;

// Mock axios before importing client
vi.mock('axios', () => {
  const mockInstance = {
    interceptors: {
      request: {
        use: vi.fn(),
      },
      response: {
        use: vi.fn(),
      },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockInstance),
      post: vi.fn(),
    },
  };
});

// Mock error reporting and performance metrics services
vi.mock('../services/errorReporting', () => ({
  errorReportingService: {
    reportError: vi.fn(),
  },
}));

vi.mock('../services/performanceMetrics', () => ({
  performanceMetricsService: {
    measureAPICall: vi.fn(),
    collectWebVitals: vi.fn(),
  },
}));

import axios from 'axios';
import { ApiClient } from './client';

const mockAxiosCreate = vi.mocked(axios.create);

describe('ApiClient', () => {
  let apiClient: ApiClient;
  let requestInterceptor:
    | ((config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig)
    | null;
  let responseErrorInterceptor: ((error: AxiosError) => Promise<never>) | null;

  beforeEach(() => {
    vi.clearAllMocks();

    // Create new client instance - this will call axios.create
    apiClient = new ApiClient();

    // Get the mock instance that was created
    const createdInstance = mockAxiosCreate.mock.results[mockAxiosCreate.mock.results.length - 1]
      ?.value as AxiosInstance;
    if (!createdInstance) {
      throw new Error('Failed to get mock axios instance');
    }

    // Capture interceptors from the mock
    const requestUseCall = (createdInstance.interceptors.request.use as ReturnType<typeof vi.fn>)
      .mock.calls[
      (createdInstance.interceptors.request.use as ReturnType<typeof vi.fn>).mock.calls.length - 1
    ];
    requestInterceptor = requestUseCall?.[0] || null;

    const responseUseCall = (createdInstance.interceptors.response.use as ReturnType<typeof vi.fn>)
      .mock.calls[
      (createdInstance.interceptors.response.use as ReturnType<typeof vi.fn>).mock.calls.length - 1
    ];
    responseErrorInterceptor = responseUseCall?.[1] || null;
  });

  describe('Error Shape Normalization', () => {
    it('should normalize nested error shape correctly', async () => {
      const nestedError: ApiError = {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Invalid input',
          http_status: 400,
          request_id: 'req-123',
          timestamp: '2024-01-01T00:00:00Z',
          details: { field: 'email' },
        },
      };

      const axiosError = {
        response: {
          status: 400,
          data: nestedError,
          headers: {},
        },
        config: {
          headers: {},
        } as InternalAxiosRequestConfig,
        isAxiosError: true,
        name: 'AxiosError',
        message: 'Request failed',
      } as unknown as AxiosError<ApiError>;

      if (!responseErrorInterceptor) {
        throw new Error('Response error interceptor not set');
      }

      try {
        await responseErrorInterceptor(axiosError);
        expect.fail('Should have rejected');
      } catch (rejectedError) {
        const apiError = rejectedError as ApiError;
        expect(apiError.error.code).toBe('VALIDATION_ERROR');
        expect(apiError.error.message).toBe('Invalid input');
        expect(apiError.error.details).toEqual({ field: 'email' });
      }
    });

    it('should normalize flat error shape correctly', async () => {
      const flatError = {
        error: 'Invalid input',
        code: 'VALIDATION_ERROR',
        details: { field: 'email' },
        timestamp: '2024-01-01T00:00:00Z',
      };

      const axiosError = {
        response: {
          status: 400,
          data: flatError,
          headers: {},
        },
        config: {
          headers: {},
        } as InternalAxiosRequestConfig,
        isAxiosError: true,
        name: 'AxiosError',
        message: 'Request failed',
      } as unknown as AxiosError;

      if (!responseErrorInterceptor) {
        throw new Error('Response error interceptor not set');
      }

      try {
        await responseErrorInterceptor(axiosError);
        expect.fail('Should have rejected');
      } catch (rejectedError) {
        const apiError = rejectedError as ApiError;
        // Flat error should be normalized to nested structure
        expect(apiError.error.code).toBe('VALIDATION_ERROR');
        expect(apiError.error.message).toBe('Invalid input');
        expect(apiError.error.details).toEqual({ field: 'email' });
      }
    });

    it('should preserve code and details from flat error shape', async () => {
      const flatError = {
        error: 'Something went wrong',
        code: 'CUSTOM_ERROR',
        details: { custom_field: 'value', nested: { data: 123 } },
      };

      const axiosError = {
        response: {
          status: 500,
          data: flatError,
          headers: {},
        },
        config: {
          headers: {},
        } as InternalAxiosRequestConfig,
        isAxiosError: true,
        name: 'AxiosError',
        message: 'Request failed',
      } as unknown as AxiosError;

      if (!responseErrorInterceptor) {
        throw new Error('Response error interceptor not set');
      }

      try {
        await responseErrorInterceptor(axiosError);
        expect.fail('Should have rejected');
      } catch (rejectedError) {
        const apiError = rejectedError as ApiError;
        // Verify code and details are preserved
        expect(apiError.error.code).toBe('CUSTOM_ERROR');
        expect(apiError.error.details).toEqual({ custom_field: 'value', nested: { data: 123 } });
      }
    });
  });

  describe('Network Error Retries', () => {
    let setTimeoutSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      vi.useFakeTimers();
      setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it.each(['post', 'patch', 'put', 'delete'])(
      'should NOT schedule a retry for %s requests on ECONNABORTED (timeout)',
      async (method) => {
        if (!responseErrorInterceptor) throw new Error('Response error interceptor not set');

        const networkError = {
          response: undefined,
          code: 'ECONNABORTED',
          message: 'timeout of 45000ms exceeded',
          config: {
            method,
            headers: {},
            _networkRetryCount: undefined,
          } as unknown as InternalAxiosRequestConfig,
          isAxiosError: true,
          name: 'AxiosError',
        } as unknown as AxiosError;

        try {
          await responseErrorInterceptor(networkError);
          expect.fail('Should have rejected');
        } catch {
          // Expected rejection — key assertion: no retry back-off timer was started
        }

        expect(setTimeoutSpy).not.toHaveBeenCalled();
      }
    );

    it.each(['post', 'patch', 'put', 'delete'])(
      'should NOT schedule a retry for %s requests on ECONNRESET',
      async (method) => {
        if (!responseErrorInterceptor) throw new Error('Response error interceptor not set');

        const networkError = {
          response: undefined,
          code: 'ECONNRESET',
          message: 'socket hang up',
          config: {
            method,
            headers: {},
            _networkRetryCount: undefined,
          } as unknown as InternalAxiosRequestConfig,
          isAxiosError: true,
          name: 'AxiosError',
        } as unknown as AxiosError;

        try {
          await responseErrorInterceptor(networkError);
          expect.fail('Should have rejected');
        } catch {
          // Expected rejection
        }

        expect(setTimeoutSpy).not.toHaveBeenCalled();
      }
    );

    it('should schedule a retry back-off for GET requests on ECONNRESET', async () => {
      if (!responseErrorInterceptor) throw new Error('Response error interceptor not set');

      const networkError = {
        response: undefined,
        code: 'ECONNRESET',
        message: 'socket hang up',
        config: {
          method: 'get',
          headers: {},
          url: '/some-resource/',
          _networkRetryCount: undefined,
        } as unknown as InternalAxiosRequestConfig,
        isAxiosError: true,
        name: 'AxiosError',
      } as unknown as AxiosError;

      // Kick off the interceptor but don't await — the retry timer will pause it
      const pendingPromise = responseErrorInterceptor(networkError).catch(() => {});

      // The retry logic awaits a setTimeout before calling this.client again;
      // advance timers to unblock it so the test doesn't hang
      await vi.runAllTimersAsync();
      await pendingPromise;

      expect(setTimeoutSpy).toHaveBeenCalledOnce();
      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 1000);
    });
  });

  describe('Tenant ID Header', () => {
    it('should add X-Tenant-ID header when tenant ID getter is set', () => {
      const tenantId = 'tenant-123';
      apiClient.setTenantIdGetter(() => tenantId);

      const config = {
        headers: {},
      } as InternalAxiosRequestConfig;

      if (!requestInterceptor) {
        throw new Error('Request interceptor not set');
      }

      const result = requestInterceptor(config);
      expect(result.headers['X-Tenant-ID']).toBe(tenantId);
    });

    it('should not add X-Tenant-ID header when tenant ID getter returns null', () => {
      apiClient.setTenantIdGetter(() => null);

      const config = {
        headers: {},
      } as InternalAxiosRequestConfig;

      if (!requestInterceptor) {
        throw new Error('Request interceptor not set');
      }

      const result = requestInterceptor(config);
      expect(result.headers['X-Tenant-ID']).toBeUndefined();
    });

    it('should not add X-Tenant-ID header when tenant ID getter is not set', () => {
      apiClient.setTenantIdGetter(null);

      const config = {
        headers: {},
      } as InternalAxiosRequestConfig;

      if (!requestInterceptor) {
        throw new Error('Request interceptor not set');
      }

      const result = requestInterceptor(config);
      expect(result.headers['X-Tenant-ID']).toBeUndefined();
    });
  });
});
