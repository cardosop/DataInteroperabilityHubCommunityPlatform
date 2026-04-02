/**
 * API Client Tests — Phase 209: fetch-based client
 *
 * Tests for FetchHttpClient: error normalization, auth headers, tenant ID,
 * token refresh, network retry, timeout, blob responses.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ApiError } from '../types/api';

// Mock dependencies
vi.mock('../services/errorReporting', () => ({
  errorReportingService: { reportError: vi.fn() },
}));
vi.mock('../services/performanceMetrics', () => ({
  performanceMetricsService: { measureAPICall: vi.fn() },
}));

// Mock crypto.randomUUID
vi.stubGlobal('crypto', { randomUUID: () => 'test-correlation-id' });

import { ApiClient } from './client';

function mockFetchResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

describe('ApiClient (fetch-based)', () => {
  let client: ApiClient;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    Object.defineProperty(document, 'cookie', { writable: true, value: '' });
    client = new ApiClient();
  });

  describe('successful requests', () => {
    it('GET returns { data, status, headers }', async () => {
      fetchMock.mockResolvedValue(mockFetchResponse({ results: [1, 2, 3] }));

      const response = await client.getClient().get<{ results: number[] }>('assets/');
      expect(response.data).toEqual({ results: [1, 2, 3] });
      expect(response.status).toBe(200);
      expect(fetchMock).toHaveBeenCalledOnce();
    });

    it('POST sends JSON body', async () => {
      fetchMock.mockResolvedValue(mockFetchResponse({ id: '123' }, 201));

      const response = await client.getClient().post('assets/', { name: 'test' });
      expect(response.data).toEqual({ id: '123' });
      expect(response.status).toBe(201);

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(init.body).toBe(JSON.stringify({ name: 'test' }));
      expect(init.method).toBe('POST');
    });

    it('handles 204 No Content (empty body)', async () => {
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

      const response = await client.getClient().delete('assets/123/');
      expect(response.data).toBeUndefined();
      expect(response.status).toBe(204);
    });

    it('handles blob responseType', async () => {
      const blob = new Blob(['test content'], { type: 'text/plain' });
      fetchMock.mockResolvedValue(new Response(blob, { status: 200 }));

      const response = await client.getClient().get('files/download/', { responseType: 'blob' });
      expect(response.data).toBeInstanceOf(Blob);
    });
  });

  describe('request headers', () => {
    it('adds Authorization header when access token is set', async () => {
      client.setAccessToken('test-token-123');
      fetchMock.mockResolvedValue(mockFetchResponse({}));

      await client.getClient().get('assets/');

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get('Authorization')).toBe('Bearer test-token-123');
    });

    it('adds X-Tenant-ID header when tenant getter is set', async () => {
      client.setTenantIdGetter(() => 'tenant-abc');
      fetchMock.mockResolvedValue(mockFetchResponse({}));

      await client.getClient().get('assets/');

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get('X-Tenant-ID')).toBe('tenant-abc');
    });

    it('adds X-Correlation-ID header', async () => {
      fetchMock.mockResolvedValue(mockFetchResponse({}));

      await client.getClient().get('assets/');

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get('X-Correlation-ID')).toBe('test-correlation-id');
    });

    it('adds Cache-Control for GET requests', async () => {
      fetchMock.mockResolvedValue(mockFetchResponse({}));

      await client.getClient().get('assets/');

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get('Cache-Control')).toBe('no-cache, no-store, must-revalidate');
    });

    it('adds CSRF token for POST requests', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrftoken=my-csrf-token',
      });
      fetchMock.mockResolvedValue(mockFetchResponse({}));

      await client.getClient().post('assets/', {});

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get('X-CSRFToken')).toBe('my-csrf-token');
    });

    it('sends credentials: include', async () => {
      fetchMock.mockResolvedValue(mockFetchResponse({}));

      await client.getClient().get('assets/');

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(init.credentials).toBe('include');
    });
  });

  describe('error normalization', () => {
    it('normalizes nested error shape { error: { code, message } }', async () => {
      fetchMock.mockResolvedValue(
        mockFetchResponse(
          { error: { code: 'NOT_FOUND', message: 'Asset not found' } },
          404,
        ),
      );

      await expect(client.getClient().get('assets/999/')).rejects.toMatchObject({
        error: {
          code: 'NOT_FOUND',
          message: 'Asset not found',
          http_status: 404,
        },
      } satisfies Partial<ApiError>);
    });

    it('normalizes flat DRF error shape { detail: "..." }', async () => {
      fetchMock.mockResolvedValue(
        mockFetchResponse({ detail: 'Not found.' }, 404),
      );

      await expect(client.getClient().get('assets/999/')).rejects.toMatchObject({
        error: {
          message: 'Not found.',
          http_status: 404,
        },
      });
    });

    it('normalizes DRF field validation error { field: ["msg"] }', async () => {
      fetchMock.mockResolvedValue(
        mockFetchResponse({ name: ['This field is required.'] }, 400),
      );

      await expect(client.getClient().post('assets/', {})).rejects.toMatchObject({
        error: {
          message: 'This field is required.',
          http_status: 400,
        },
      });
    });

    it('handles non-JSON error response', async () => {
      fetchMock.mockResolvedValue(
        new Response('Internal Server Error', {
          status: 500,
          headers: { 'Content-Type': 'text/plain' },
        }),
      );

      await expect(client.getClient().get('assets/')).rejects.toMatchObject({
        error: {
          code: 'UNKNOWN_ERROR',
          http_status: 500,
        },
      });
    });
  });

  describe('401 refresh and retry', () => {
    it('refreshes token and retries on 401', async () => {
      client.setRefreshToken('refresh-token-123');

      fetchMock
        // First call: 401
        .mockResolvedValueOnce(mockFetchResponse({ detail: 'Unauthorized' }, 401))
        // Refresh call: success
        .mockResolvedValueOnce(
          mockFetchResponse({ access_token: 'new-token', refresh_token: 'new-refresh' }),
        )
        // Retry: success
        .mockResolvedValueOnce(mockFetchResponse({ results: [] }));

      const response = await client.getClient().get('assets/');
      expect(response.data).toEqual({ results: [] });
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    it('clears tokens when refresh fails', async () => {
      client.setRefreshToken('bad-refresh');

      fetchMock
        // First call: 401
        .mockResolvedValueOnce(mockFetchResponse({ detail: 'Unauthorized' }, 401))
        // Refresh call: fails
        .mockResolvedValueOnce(mockFetchResponse({ detail: 'Invalid token' }, 401));

      await expect(client.getClient().get('assets/')).rejects.toMatchObject({
        error: { http_status: 401 },
      });
      expect(client.getAccessToken()).toBeNull();
    });
  });

  describe('network retry', () => {
    it('retries GET on network error (max 2)', async () => {
      fetchMock
        .mockRejectedValueOnce(new TypeError('Failed to fetch'))
        .mockRejectedValueOnce(new TypeError('Failed to fetch'))
        .mockResolvedValueOnce(mockFetchResponse({ ok: true }));

      const response = await client.getClient().get('health/');
      expect(response.data).toEqual({ ok: true });
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    it('does NOT retry POST on network error', async () => {
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

      await expect(client.getClient().post('assets/', {})).rejects.toMatchObject({
        error: { code: 'NETWORK_ERROR' },
      });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe('timeout', () => {
    it('aborts request after timeout', async () => {
      fetchMock.mockImplementation(
        () => new Promise((_, reject) => {
          setTimeout(() => reject(new DOMException('Aborted', 'AbortError')), 10);
        }),
      );

      await expect(
        client.getClient().get('slow/', { timeout: 5 }),
      ).rejects.toMatchObject({
        error: { code: 'TIMEOUT' },
      });
    });
  });

  describe('token management', () => {
    it('getAccessToken returns null initially', () => {
      expect(client.getAccessToken()).toBeNull();
    });

    it('setAccessToken / getAccessToken round-trip', () => {
      client.setAccessToken('tok');
      expect(client.getAccessToken()).toBe('tok');
    });

    it('clearTokens resets both tokens', () => {
      client.setAccessToken('a');
      client.setRefreshToken('r');
      client.clearTokens();
      expect(client.getAccessToken()).toBeNull();
    });
  });
});
