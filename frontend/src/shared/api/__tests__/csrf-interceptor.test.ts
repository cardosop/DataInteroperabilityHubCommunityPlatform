/**
 * CSRF Token Interceptor Tests — Phase 50.10
 *
 * Validates the Axios request interceptor adds X-CSRFToken on
 * state-changing methods (POST/PUT/PATCH/DELETE) but NOT on
 * safe methods (GET/HEAD/OPTIONS).
 */

import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { ApiClient } from '../client';

describe('CSRF token interceptor', () => {
  const CSRF_TOKEN = 'test-csrf-token-abc123';

  beforeEach(() => {
    // Set a mock csrftoken cookie
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: `sessionid=xyz; csrftoken=${CSRF_TOKEN}; other=val`,
    });
  });

  afterEach(() => {
    Object.defineProperty(document, 'cookie', { writable: true, value: '' });
  });

  /**
   * Helper: create a fresh ApiClient, make a request, capture the config
   * that the interceptor produces (without actually hitting the network).
   */
  async function captureRequestConfig(method: string, url = '/test') {
    const client = new ApiClient();
    // Replace the underlying Axios adapter with one that captures the config
    let capturedConfig: Record<string, unknown> | null = null;
    client['client'].defaults.adapter = async (config) => {
      capturedConfig = config as unknown as Record<string, unknown>;
      // Return a minimal valid AxiosResponse to prevent errors
      return {
        data: {},
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      } as never;
    };

    try {
      await (client as unknown as { client: { request: (c: object) => Promise<unknown> } }).client.request({
        method,
        url,
      });
    } catch {
      // Ignore network/adapter errors
    }

    return capturedConfig;
  }

  it('sets X-CSRFToken on POST requests', async () => {
    const config = await captureRequestConfig('POST');
    expect(config).not.toBeNull();
    const headers = (config as Record<string, unknown>).headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBe(CSRF_TOKEN);
  });

  it('sets X-CSRFToken on PUT requests', async () => {
    const config = await captureRequestConfig('PUT');
    const headers = (config as Record<string, unknown>)?.headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBe(CSRF_TOKEN);
  });

  it('sets X-CSRFToken on PATCH requests', async () => {
    const config = await captureRequestConfig('PATCH');
    const headers = (config as Record<string, unknown>)?.headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBe(CSRF_TOKEN);
  });

  it('sets X-CSRFToken on DELETE requests', async () => {
    const config = await captureRequestConfig('DELETE');
    const headers = (config as Record<string, unknown>)?.headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBe(CSRF_TOKEN);
  });

  it('does NOT set X-CSRFToken on GET requests', async () => {
    const config = await captureRequestConfig('GET');
    const headers = (config as Record<string, unknown>)?.headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBeUndefined();
  });

  it('does NOT set X-CSRFToken when cookie is absent', async () => {
    Object.defineProperty(document, 'cookie', { writable: true, value: 'sessionid=xyz' });
    const config = await captureRequestConfig('POST');
    const headers = (config as Record<string, unknown>)?.headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBeUndefined();
  });
});
