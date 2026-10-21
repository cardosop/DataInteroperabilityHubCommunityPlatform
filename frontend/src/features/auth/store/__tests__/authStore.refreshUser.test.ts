// @vitest-environment node
// The REAL fetch/AbortController pair (node's) drives the apiClient's
// transport; jsdom's AbortSignal would make every fetch reject with
// "Expected signal to be an instance of AbortSignal".
/**
 * W5.3 (oss-release-remediation R2-F4) — refreshUser non-destructive pins.
 *
 * The pre-fix refreshUser treated EVERY failure as session death: a
 * transient network error (or a 5xx from a busy backend) cleared the
 * user, the tenant, and fired the auth-failed identity boundary — users
 * were logged out by backend hiccups. The fix: only an unrecoverable
 * auth failure (401 after a failed refresh) is destructive; network and
 * 5xx failures retry once, then keep the current state.
 *
 * REAL store + REAL apiClient + REAL authService against a REAL local
 * HTTP server (connection-level failures via socket destruction — the
 * genuine network-error class). VITE_API_BASE_URL is the configuration
 * seam; the identity-cache bus is the REAL one.
 */

import * as http from 'node:http';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { User } from '../../../shared/types/auth';

type MeBehavior = { kind: 'destroy' } | { kind: 'respond'; status: number; body: unknown };

interface MeServer {
  baseUrl: string;
  meHits: number;
  enqueueMe(...behaviors: MeBehavior[]): void;
  enqueueRefresh(status: number, body: unknown): void;
  reset(): void;
  close(): Promise<void>;
}

function startMeServer(): Promise<MeServer> {
  let meHits = 0;
  const meQueue: MeBehavior[] = [];
  const refreshQueue: Array<{ status: number; body: unknown }> = [];

  const server = http.createServer((req, res) => {
    req.on('error', () => {});
    res.on('error', () => {});
    const url = new URL(req.url ?? '/', 'http://localhost');
    if (req.method === 'GET' && url.pathname === '/api/v1/auth/me/') {
      meHits += 1;
      const next = meQueue.shift() ?? { kind: 'respond', status: 200, body: {} };
      if (next.kind === 'destroy') {
        req.socket.destroy();
        return;
      }
      res.writeHead(next.status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(next.body));
      return;
    }
    if (req.method === 'POST' && url.pathname === '/api/v1/auth/refresh/') {
      const next = refreshQueue.shift() ?? { status: 200, body: { access_token: 'tok' } };
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
        get meHits() {
          return meHits;
        },
        enqueueMe: (...behaviors) => meQueue.push(...behaviors),
        enqueueRefresh: (status, body) => refreshQueue.push({ status, body }),
        reset: () => {
          // Queue hygiene: leftover behaviors from one test must never
          // leak into the next test's traffic.
          meQueue.length = 0;
          refreshQueue.length = 0;
          meHits = 0;
        },
        close: () =>
          new Promise<void>((res2) => {
            server.close(() => res2());
          }),
      });
    });
  });
}

function userOf(id: string, extra?: Partial<User>): User {
  return {
    id,
    email: `${id}@example.com`,
    name: 'User',
    roles: [],
    tenant_id: 'tenant-t1',
    is_active: true,
    ...extra,
  };
}

describe('authStore refreshUser (W5.3 non-destructive)', () => {
  let server: MeServer;
  let store: typeof import('../authStore');
  let apiClientMod: typeof import('../../../../shared/api/client');
  let cacheIdentityMod: typeof import('../../../../shared/services/cacheIdentity');

  const keptUser = userOf('kept');

  beforeAll(async () => {
    server = await startMeServer();
    vi.stubEnv('VITE_API_BASE_URL', server.baseUrl);
    localStorage.setItem('user', JSON.stringify(keptUser));
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

  beforeEach(() => {
    server.reset();
    localStorage.clear();
    store.useAuthStore.setState({
      user: keptUser,
      active_tenant_id: null,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });
    apiClientMod.apiClient._suppressAuthRedirect = true;
  });

  it('a transient network failure retries once and applies the fresh user (non-destructive)', async () => {
    const boundaries: string[] = [];
    const unregister = cacheIdentityMod.registerIdentityCacheInvalidator((b) =>
      boundaries.push(b),
    );
    try {
      // The apiClient itself retries safe GETs twice on network errors
      // (1s + 2s backoff) — three destroyed sockets exhaust ONE
      // refreshUser attempt; the fourth request serves the fresh user.
      server.enqueueMe(
        { kind: 'destroy' },
        { kind: 'destroy' },
        { kind: 'destroy' },
        { kind: 'respond', status: 200, body: userOf('fresh') },
      );

      await store.useAuthStore.getState().refreshUser();

      expect(store.useAuthStore.getState().user?.id).toBe('fresh');
      expect(store.useAuthStore.getState().isAuthenticated).toBe(true);
      expect(server.meHits).toBe(4);
      expect(boundaries).toEqual([]);
    } finally {
      unregister();
    }
  });

  it('a persistent 5xx keeps the current state and never logs the user out', async () => {
    const boundaries: string[] = [];
    const unregister = cacheIdentityMod.registerIdentityCacheInvalidator((b) =>
      boundaries.push(b),
    );
    try {
      server.enqueueMe(
        { kind: 'respond', status: 503, body: { detail: 'backend down' } },
        { kind: 'respond', status: 503, body: { detail: 'backend down' } },
      );

      await store.useAuthStore.getState().refreshUser();

      expect(store.useAuthStore.getState().user?.id).toBe('kept');
      expect(store.useAuthStore.getState().isAuthenticated).toBe(true);
      expect(store.useAuthStore.getState().user?.tenant_id).toBe('tenant-t1');
      expect(boundaries).toEqual([]);
    } finally {
      unregister();
    }
  });

  it('an unrecoverable auth failure still clears destructively (regression)', async () => {
    const boundaries: string[] = [];
    const unregister = cacheIdentityMod.registerIdentityCacheInvalidator((b) =>
      boundaries.push(b),
    );
    try {
      server.enqueueRefresh(401, { detail: 'refresh token revoked' });
      server.enqueueMe({ kind: 'respond', status: 401, body: { detail: 'stale' } });

      await store.useAuthStore.getState().refreshUser();

      expect(store.useAuthStore.getState().user).toBeNull();
      expect(store.useAuthStore.getState().isAuthenticated).toBe(false);
      expect(boundaries).toContain('auth-failed');
    } finally {
      unregister();
    }
  });

  it('feature_tenant_switch_enabled=false removes the persisted override', async () => {
    localStorage.setItem('active_tenant_id', 'tenant-stale-9');
    store.useAuthStore.setState({ active_tenant_id: 'tenant-stale-9' });

    server.enqueueMe({
      kind: 'respond',
      status: 200,
      body: userOf('kept', { feature_tenant_switch_enabled: false }),
    });

    await store.useAuthStore.getState().refreshUser();

    expect(store.useAuthStore.getState().active_tenant_id).toBeNull();
    expect(localStorage.getItem('active_tenant_id')).toBeNull();
  });

  it('the userOverride path stays local (no network, merged apply) — regression', async () => {
    await store.useAuthStore.getState().refreshUser({ name: 'Edited Name' });
    expect(store.useAuthStore.getState().user?.name).toBe('Edited Name');
    expect(store.useAuthStore.getState().user?.id).toBe('kept');
    expect(server.meHits).toBe(0);
  });
});
