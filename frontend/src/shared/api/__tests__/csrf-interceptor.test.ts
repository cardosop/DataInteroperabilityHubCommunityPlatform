/**
 * CSRF Token Middleware Tests — Phase 50.10 (updated Phase 209: fetch-based)
 *
 * Validates the API client request middleware adds X-CSRFToken on
 * state-changing methods (POST/PUT/PATCH/DELETE) but NOT on
 * safe methods (GET/HEAD/OPTIONS).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../client';

// Mock dependencies that ApiClient imports
vi.mock('../../services/errorReporting', () => ({
  errorReportingService: { reportError: vi.fn() },
}));
vi.mock('../../services/performanceMetrics', () => ({
  performanceMetricsService: { measureAPICall: vi.fn() },
}));

describe('CSRF token middleware', () => {
  const CSRF_TOKEN = 'test-csrf-token-abc123';
  let capturedHeaders: Headers | null = null;
  let capturedMethod: string | null = null;

  beforeEach(() => {
    capturedHeaders = null;
    capturedMethod = null;

    // Set a mock csrftoken cookie
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: `sessionid=xyz; csrftoken=${CSRF_TOKEN}; other=val`,
    });

    // Mock fetch to capture request details
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers as HeadersInit);
      capturedMethod = init?.method ?? 'GET';
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }));
  });

  afterEach(() => {
    Object.defineProperty(document, 'cookie', { writable: true, value: '' });
    vi.restoreAllMocks();
  });

  async function makeRequest(method: string) {
    const client = new ApiClient();
    const httpClient = client.getClient();
    switch (method) {
      case 'POST': await httpClient.post('/test', {}); break;
      case 'PUT': await httpClient.put('/test', {}); break;
      case 'PATCH': await httpClient.patch('/test', {}); break;
      case 'DELETE': await httpClient.delete('/test'); break;
      case 'GET': await httpClient.get('/test'); break;
    }
  }

  it('sets X-CSRFToken on POST requests', async () => {
    await makeRequest('POST');
    expect(capturedHeaders?.get('X-CSRFToken')).toBe(CSRF_TOKEN);
  });

  it('sets X-CSRFToken on PUT requests', async () => {
    await makeRequest('PUT');
    expect(capturedHeaders?.get('X-CSRFToken')).toBe(CSRF_TOKEN);
  });

  it('sets X-CSRFToken on PATCH requests', async () => {
    await makeRequest('PATCH');
    expect(capturedHeaders?.get('X-CSRFToken')).toBe(CSRF_TOKEN);
  });

  it('sets X-CSRFToken on DELETE requests', async () => {
    await makeRequest('DELETE');
    expect(capturedHeaders?.get('X-CSRFToken')).toBe(CSRF_TOKEN);
  });

  it('does NOT set X-CSRFToken on GET requests', async () => {
    await makeRequest('GET');
    expect(capturedHeaders?.get('X-CSRFToken')).toBeNull();
  });

  it('does NOT set X-CSRFToken when cookie is absent', async () => {
    Object.defineProperty(document, 'cookie', { writable: true, value: 'sessionid=xyz' });
    await makeRequest('POST');
    expect(capturedHeaders?.get('X-CSRFToken')).toBeNull();
  });
});
