// @vitest-environment node
// The REAL fetch/AbortController pair (node's) drives the apiClient's
// transport; jsdom's AbortSignal would make every fetch reject with
// "Expected signal to be an instance of AbortSignal".
/**
 * W5.3 (oss-release-remediation R2-F4) — auth init race pins.
 *
 * The REAL store, REAL authService and REAL apiClient run against a REAL
 * local HTTP server (VITE_API_BASE_URL is the only configuration seam —
 * no module mocks, no fetch fakes). The server defers /auth/me/
 * responses so the pins can interleave initialize() with logout() and
 * with a second initialize() exactly the way production races them.
 *
 * Pins:
 *  - late-init-no-reauth: a deferred /auth/me/ success arriving AFTER a
 *    logout must never re-authenticate the session (pre-fix it did —
 *    the retry loop kept running with no cancellation).
 *  - stale-401-no-clobber: a stale init's 401 arriving AFTER a newer
 *    init succeeded must not clear the fresh identity (pre-fix the old
 *    loop's clearAuthState() logged the new session out).
 */

import * as http from 'node:http';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';
import type { User } from '../../../shared/types/auth';

interface DeferredResponse {
  resolve: (payload: { status: number; body: unknown }) => void;
}

interface AuthServer {
  baseUrl: string;
  meRequests: number;
  nextMe(): Promise<DeferredResponse>;
  close(): Promise<void>;
}

function startAuthServer(): Promise<AuthServer> {
  const meWaiters: Array<(r: DeferredResponse) => void> = [];
  const meQueue: DeferredResponse[] = [];
  let meRequests = 0;

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    if (req.method === 'POST' && url.pathname === '/api/v1/auth/refresh/') {
      const token = jwtFor('tenant-t1');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ access_token: token }));
      return;
    }
    if (req.method === 'POST' && url.pathname === '/api/v1/auth/logout/') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{}');
      return;
    }
    if (req.method === 'GET' && url.pathname === '/api/v1/auth/me/') {
      meRequests += 1;
      const record: DeferredResponse = {
        resolve: (payload) => {
          res.writeHead(payload.status, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(payload.body));
        },
      };
      const waiter = meWaiters.shift();
      if (waiter) waiter(record);
      else meQueue.push(record);
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
        get meRequests() {
          return meRequests;
        },
        nextMe: () => {
          const next = meQueue.shift();
          if (next) return Promise.resolve(next);
          return new Promise((res2) => meWaiters.push(res2));
        },
        close: () =>
          new Promise<void>((res2) => {
            server.close(() => res2());
          }),
      });
    });
  });
}

function jwtFor(tenantId: string): string {
  const payload = btoa(JSON.stringify({ tenant_id: tenantId, exp: 9999999999 }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  return `header.${payload}.sig`;
}

function userOf(id: string): User {
  return {
    id,
    email: `${id}@example.com`,
    name: 'User',
    roles: [],
    tenant_id: 'tenant-t1',
    is_active: true,
  };
}

describe('authStore initialize races (W5.3)', () => {
  let server: AuthServer;
  let store: typeof import('../authStore');
  let apiClientMod: typeof import('../../../../shared/api/client');
  let cacheIdentityMod: typeof import('../../../../shared/services/cacheIdentity');

  const storedUser = userOf('stored');

  beforeAll(async () => {
    server = await startAuthServer();
    vi.stubEnv('VITE_API_BASE_URL', server.baseUrl);
    // Seed BEFORE the imports: the fresh store hydrates synchronously
    // from localStorage at module evaluation (Phase 213.I).
    localStorage.setItem('user', JSON.stringify(storedUser));
    localStorage.setItem('auth_mode', 'body');
    vi.resetModules();
    store = await import('../authStore');
    apiClientMod = await import('../../../../shared/api/client');
    cacheIdentityMod = await import('../../../../shared/services/cacheIdentity');
  });

  afterAll(async () => {
    vi.unstubAllEnvs();
    vi.resetModules();
    localStorage.clear();
    await server.close();
  });

  it('a late initialize response cannot re-authenticate a logged-out session (late-init-no-reauth)', async () => {
    store.useAuthStore.setState({ user: storedUser, isAuthenticated: true, isLoading: false });
    const boundaries: string[] = [];
    const unregister = cacheIdentityMod.registerIdentityCacheInvalidator((b) =>
      boundaries.push(b),
    );
    try {
      const initPromise = store.useAuthStore.getState().initialize();
      const meRequest = await server.nextMe(); // the init's /auth/me/ is in flight

      await store.useAuthStore.getState().logout();

      // The pre-W5.3 store kept running the init loop after logout —
      // this 200 would re-authenticate the session.
      meRequest.resolve({ status: 200, body: userOf('late') });
      await initPromise;

      expect(store.useAuthStore.getState().user).toBeNull();
      expect(store.useAuthStore.getState().isAuthenticated).toBe(false);
      // The identity boundary fired exactly once — for the logout.
      expect(boundaries).toEqual(['logout']);
    } finally {
      unregister();
    }
  });

  it('a stale init 401 cannot clear a newer successful init (generation counter)', async () => {
    store.useAuthStore.setState({ user: storedUser, isAuthenticated: true, isLoading: false });

    const firstInit = store.useAuthStore.getState().initialize();
    const firstMe = await server.nextMe();

    const secondInit = store.useAuthStore.getState().initialize();
    const secondMe = await server.nextMe();

    // The newer init succeeds first.
    secondMe.resolve({ status: 200, body: userOf('fresh') });
    await secondInit;
    expect(store.useAuthStore.getState().user?.id).toBe('fresh');

    // The older init's session is stale by the time it resolves — its
    // 401 must NOT clearAuthState() over the fresh identity.
    firstMe.resolve({ status: 401, body: { detail: 'stale session' } });
    await firstInit;

    expect(store.useAuthStore.getState().user?.id).toBe('fresh');
    expect(store.useAuthStore.getState().isAuthenticated).toBe(true);
    // The stale init must not have bumped the user write sequence either
    // (a clobber guard on top of the generation guard).
    expect(store.useAuthStore.getState().user?.email).toBe('fresh@example.com');
  });

  it('initialize returns the hydrated user after a clean run (regression)', async () => {
    store.useAuthStore.setState({ user: storedUser, isAuthenticated: true, isLoading: false });
    const initPromise = store.useAuthStore.getState().initialize();
    const meRequest = await server.nextMe();
    meRequest.resolve({ status: 200, body: userOf('hydrated') });
    await initPromise;
    expect(store.useAuthStore.getState().user?.id).toBe('hydrated');
    expect(store.useAuthStore.getState().isAuthenticated).toBe(true);
    expect(apiClientMod.apiClient.getAccessToken()).toBeTruthy();
  });
});
