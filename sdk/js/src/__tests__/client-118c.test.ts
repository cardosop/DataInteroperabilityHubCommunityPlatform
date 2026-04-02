/**
 * Phase 118C — JS SDK Critical Fixes Tests
 *
 * 118C.1: authType bearer|apikey — ApiKey header format
 * 118C.2: Request interceptor camelCase → snake_case
 * 118C.3: Response interceptor snake_case → camelCase
 * 118C.4: Async race condition fix in token refresh
 */

import axios from 'axios';
import { DataHubClient } from '../client';
import { camelToSnake, snakeToCamel } from '../caseTransform';

jest.mock('axios');

describe('Phase 118C — JS SDK Critical Fixes', () => {
  let mockAxiosInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    mockAxiosInstance = {
      request: jest.fn(),
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() },
      },
    };
    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
  });

  // ===========================================================
  // 118C.1 — authType: 'bearer' | 'apikey'
  // ===========================================================
  describe('118C.1 — authType config', () => {
    it('should default to bearer auth', () => {
      new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'tok_123',
      });

      const requestInterceptor =
        mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} as Record<string, string> };
      requestInterceptor(config);

      expect(config.headers.Authorization).toBe('Bearer tok_123');
    });

    it('should send ApiKey header when authType is apikey', () => {
      new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'key_abc',
        authType: 'apikey',
      });

      const requestInterceptor =
        mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} as Record<string, string> };
      requestInterceptor(config);

      expect(config.headers.Authorization).toBe('ApiKey key_abc');
    });

    it('should send Bearer header when authType is bearer', () => {
      new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'jwt_xyz',
        authType: 'bearer',
      });

      const requestInterceptor =
        mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} as Record<string, string> };
      requestInterceptor(config);

      expect(config.headers.Authorization).toBe('Bearer jwt_xyz');
    });
  });

  // ===========================================================
  // 118C.2 — camelCase → snake_case request transform
  // ===========================================================
  describe('118C.2 — camelToSnake transform', () => {
    it('should convert flat camelCase keys to snake_case', () => {
      expect(camelToSnake({ firstName: 'John', lastName: 'Doe' }))
        .toEqual({ first_name: 'John', last_name: 'Doe' });
    });

    it('should convert nested objects recursively', () => {
      expect(camelToSnake({
        tenantId: 'abc',
        metadata: { createdBy: 'admin', lastModifiedAt: '2026-01-01' },
      })).toEqual({
        tenant_id: 'abc',
        metadata: { created_by: 'admin', last_modified_at: '2026-01-01' },
      });
    });

    it('should convert arrays of objects', () => {
      expect(camelToSnake({
        items: [{ planSlug: 'pro' }, { planSlug: 'free' }],
      })).toEqual({
        items: [{ plan_slug: 'pro' }, { plan_slug: 'free' }],
      });
    });

    it('should leave primitives unchanged', () => {
      expect(camelToSnake(42)).toBe(42);
      expect(camelToSnake('hello')).toBe('hello');
      expect(camelToSnake(null)).toBe(null);
      expect(camelToSnake(undefined)).toBe(undefined);
    });

    it('should preserve already_snake_case keys', () => {
      expect(camelToSnake({ already_snake: 'ok' }))
        .toEqual({ already_snake: 'ok' });
    });

    it('should handle request interceptor wiring', () => {
      new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'tok',
      });

      // First interceptor is auth, second is case transform
      const calls = mockAxiosInstance.interceptors.request.use.mock.calls;
      expect(calls.length).toBeGreaterThanOrEqual(2);

      const caseInterceptor = calls[1][0];
      const config = {
        data: { planSlug: 'pro', metadataJson: { createdBy: 'admin' } },
        headers: {},
      };
      const result = caseInterceptor(config);
      expect(result.data).toEqual({
        plan_slug: 'pro',
        metadata_json: { created_by: 'admin' },
      });
    });
  });

  // ===========================================================
  // 118C.3 — snake_case → camelCase response transform
  // ===========================================================
  describe('118C.3 — snakeToCamel transform', () => {
    it('should convert flat snake_case keys to camelCase', () => {
      expect(snakeToCamel({ first_name: 'John', last_name: 'Doe' }))
        .toEqual({ firstName: 'John', lastName: 'Doe' });
    });

    it('should convert nested objects recursively', () => {
      expect(snakeToCamel({
        tenant_id: 'abc',
        metadata_json: { created_by: 'admin', last_modified_at: '2026-01-01' },
      })).toEqual({
        tenantId: 'abc',
        metadataJson: { createdBy: 'admin', lastModifiedAt: '2026-01-01' },
      });
    });

    it('should convert arrays of objects', () => {
      expect(snakeToCamel({
        items: [{ plan_slug: 'pro' }, { plan_slug: 'free' }],
      })).toEqual({
        items: [{ planSlug: 'pro' }, { planSlug: 'free' }],
      });
    });

    it('should leave primitives unchanged', () => {
      expect(snakeToCamel(42)).toBe(42);
      expect(snakeToCamel('hello')).toBe('hello');
      expect(snakeToCamel(null)).toBe(null);
    });

    it('should handle response interceptor wiring', () => {
      new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'tok',
      });

      // First response interceptor call: success handler is [0][0]
      const successHandler =
        mockAxiosInstance.interceptors.response.use.mock.calls[0][0];
      const response = {
        data: { plan_slug: 'pro', metadata_json: { created_by: 'admin' } },
        status: 200,
        headers: {},
      };
      const result = successHandler(response);
      expect(result.data).toEqual({
        planSlug: 'pro',
        metadataJson: { createdBy: 'admin' },
      });
    });
  });

  // ===========================================================
  // 118C.4 — Async race condition fix in token refresh
  // ===========================================================
  describe('118C.4 — Token refresh race condition', () => {
    it('should serialize concurrent 401 token refresh attempts', async () => {
      const client = new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'expired-token',
      });

      let refreshCallCount = 0;
      client.setTokenRefreshCallback(async () => {
        refreshCallCount++;
        return 'new-token';
      });

      const errorInterceptor =
        mockAxiosInstance.interceptors.response.use.mock.calls[0][1];

      // Simulate two concurrent 401 errors
      const error401 = {
        response: { status: 401, data: {} },
        config: { headers: { Authorization: '' } },
      };

      mockAxiosInstance.request.mockResolvedValue({ data: 'ok' });

      // Fire two concurrent refresh attempts
      const p1 = errorInterceptor({ ...error401 });
      const p2 = errorInterceptor({ ...error401 });

      await Promise.all([p1, p2]);

      // Token refresh should have been called only once
      // (the second request should have waited for the first)
      expect(refreshCallCount).toBe(1);
    });

    it('should propagate refresh failure to all waiting requests', async () => {
      const client = new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'expired-token',
      });

      client.setTokenRefreshCallback(async () => {
        throw new Error('refresh failed');
      });

      const errorInterceptor =
        mockAxiosInstance.interceptors.response.use.mock.calls[0][1];

      const error401 = {
        response: { status: 401, data: {} },
        config: { headers: { Authorization: '' } },
      };

      // Both should reject with UnauthorizedError
      await expect(errorInterceptor({ ...error401 })).rejects.toThrow();
      await expect(errorInterceptor({ ...error401 })).rejects.toThrow();
    });
  });
});
