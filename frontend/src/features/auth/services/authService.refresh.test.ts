// @vitest-environment node
// The REAL fetch/AbortController pair (node's) drives the apiClient's
// transport; jsdom's AbortSignal would make every fetch reject with
// "Expected signal to be an instance of AbortSignal".
/**
 * W5.3 (oss-release-remediation R2-F4) — single-flight refresh pins.
 *
 * The proactive refresh (authService.refreshAccessToken — used by
 * initialize's cold-start loop) and the 401-interceptor refresh
 * (apiClient's) must share ONE in-flight /auth/refresh/ request. The
 * pre-fix tree had TWO refresh implementations: the apiClient one
 * single-flighted, the authService one did not — every cold start plus
 * a concurrent 401 storm issued duplicate refreshes.
 *
 * These pins run the REAL service + client against a REAL local HTTP
 * server that counts every /auth/refresh/ it receives. VITE_API_BASE_URL
 * is the only configuration seam.
 */

import * as http from 'node:http';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const TOKEN = `header.${btoa(JSON.stringify({ tenant_id: 'tenant-t1', exp: 9999999999 }))
  .replace(/\+/g, '-')
  .replace(/\//g, '_')}.sig`;

interface RefreshServer {
  baseUrl: string;
  count(): number;
  enqueue(status: number, body: unknown): void;
  reset(): void;
  close(): Promise<void>;
}

function startRefreshServer(): Promise<RefreshServer> {
  let hits = 0;
  const queue: Array<{ status: number; body: unknown }> = [];

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    if (req.method === 'POST' && url.pathname === '/api/v1/auth/refresh/') {
      hits += 1;
      const next = queue.shift() ?? { status: 200, body: { access_token: TOKEN } };
      res.writeHead(next.status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(next.body));
      return;
    }
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end('{"detail":"not found"}');
  });

  return new Promise((resolve, reject) => {
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address();
      if (addr === null || typeof addr === 'string') {
        reject(new Error('failed to bind test server'));
        return;
      }
      resolve({
        baseUrl: `http://127.0.0.1:${addr.port}/api/v1`,
        count: () => hits,
        enqueue: (status, body) => queue.push({ status, body }),
        reset: () => {
          hits = 0;
          queue.length = 0;
        },
        close: () =>
          new Promise<void>((res2) => {
            server.close(() => res2());
          }),
      });
    });
  });
}

describe('authService refresh single-flight (W5.3)', () => {
  let server: RefreshServer;
  let authService: typeof import('../authService');
  let apiClient: typeof import('../../../shared/api/client');

  beforeAll(async () => {
    server = await startRefreshServer();
    vi.stubEnv('VITE_API_BASE_URL', server.baseUrl);
    vi.resetModules();
    authService = await import('./authService');
    apiClient = await import('../../../shared/api/client');
  });

  afterAll(async () => {
    vi.unstubAllEnvs();
    vi.resetModules();
    await server.close();
  });

  beforeEach(() => {
    server.reset();
  });

  it('concurrent proactive refreshes issue ONE request (single-flight)', async () => {
    const results = await Promise.all([
      authService.authService.refreshAccessToken(),
      authService.authService.refreshAccessToken(),
      authService.authService.refreshAccessToken(),
    ]);
    expect(results).toEqual([TOKEN, TOKEN, TOKEN]);
    expect(server.count()).toBe(1);
  });

  it('the 401-retry path and the proactive refresh share the same flight', async () => {
    const results = await Promise.all([
      apiClient.apiClient.refreshAccessToken(),
      authService.authService.refreshAccessToken(),
    ]);
    expect(results).toEqual([TOKEN, TOKEN]);
    expect(server.count()).toBe(1);
    // The shared flight landed the token in the client (both paths agree).
    expect(apiClient.apiClient.getAccessToken()).toBe(TOKEN);
  });

  it('a failed refresh clears the flight so the next call retries', async () => {
    server.enqueue(500, { detail: 'refresh backend down' });
    await expect(authService.authService.refreshAccessToken()).rejects.toMatchObject({
      response: { status: 500 },
    });
    // No stale promise retained — a fresh attempt hits the server again.
    await expect(authService.authService.refreshAccessToken()).resolves.toBe(TOKEN);
  });

  it('refresh failures keep the response status for retryable classification', async () => {
    server.enqueue(429, { detail: 'rate limited' });
    await expect(authService.authService.refreshAccessToken()).rejects.toMatchObject({
      response: { status: 429 },
    });
    server.enqueue(503, { detail: 'unavailable' });
    await expect(authService.authService.refreshAccessToken()).rejects.toMatchObject({
      response: { status: 503 },
    });
  });
});
