/**
 * W5.3 (oss-release-remediation R2-F3) — SSE-open pins.
 *
 * The notification stream must actually OPEN against a real server for
 * the active tenant: a real HTTP server implements the backend's SSE
 * protocol (200 + text/event-stream + `event: ready` + comment pings)
 * and the hook's REAL fetch drives the wire (the hook is fetch-based —
 * the browser's native EventSource cannot attach headers and ignores
 * `withCredentials` for cookies on current Chromium; measured against
 * the real stack). The REAL auth store seeds the tenant, the REAL
 * apiClient provides the base URL and the operator token (via the
 * stubbed VITE_API_BASE_URL, the configuration seam), and a REAL
 * QueryClient observes the `notification.created` invalidation. No
 * mocks of any unit under test.
 *
 * Pre-fix RED: the hook gated on `useAuthStore.getState().accessToken` —
 * a store field that is never written — so the tenant was always null
 * and no stream ever opened.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import * as http from 'node:http';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { User } from '../../../shared/types/auth';

// ---------------------------------------------------------------------------
// Realm shim (this file only): jsdom 29's fetch rejects jsdom's OWN
// AbortSignal ("Expected signal to be an instance of AbortSignal" — its
// bundled undici validates against a different realm's class). The shim
// forwards to the REAL fetch with the signal dropped: every request in
// this file still travels the real network to the real server and bodies
// still stream incrementally (verified); only the abort-on-timeout
// validation is inexpressible, and no assertion here depends on it (all
// server responses are immediate; close-on-unmount is pinned through the
// no-reconnect contract instead of the wire). Same adaptation class as
// setup.ts's localStorage shim.
// ---------------------------------------------------------------------------
const realFetch = globalThis.fetch.bind(globalThis);
globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
  if (!init?.signal) return realFetch(input, init);
  const { signal: _signal, ...rest } = init;
  return realFetch(input, rest);
};

interface StreamRequest {
  url: string;
  tenantId: string | null;
  authorization: string | null;
  res: http.ServerResponse;
}

interface SseServer {
  baseUrl: string;
  requests: StreamRequest[];
  nextStreamRequest(): Promise<StreamRequest>;
  pushEvent(eventType: string, data: Record<string, unknown>): void;
  closeStreams(): Promise<void>;
  close(): Promise<void>;
}

function startSseServer(): Promise<SseServer> {
  const requests: StreamRequest[] = [];
  const waiters: Array<(req: StreamRequest) => void> = [];
  const responses: http.ServerResponse[] = [];

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    if (url.pathname === '/api/v1/notifications/stream/') {
      const record: StreamRequest = {
        url: req.url ?? '',
        tenantId: url.searchParams.get('tenant_id'),
        authorization: req.headers.authorization ?? null,
        res,
      };
      requests.push(record);
      responses.push(res);
      const waiter = waiters.shift();
      if (waiter) waiter(record);
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      });
      // Mirror the backend's first frame (stream_views.py).
      res.write('event: ready\ndata: {}\n\n');
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
        requests,
        nextStreamRequest: () => {
          const next = requests.shift();
          if (next) return Promise.resolve(next);
          return new Promise((res2) => {
            // The waiter path must ALSO consume the record — otherwise
            // the same request is returned twice (the next caller shifts
            // the stale entry).
            waiters.push((record) => {
              const idx = requests.indexOf(record);
              if (idx !== -1) requests.splice(idx, 1);
              res2(record);
            });
          });
        },
        pushEvent: (eventType, data) => {
          const body = JSON.stringify(data);
          responses.forEach((res) => {
            res.write(`event: ${eventType}\ndata: ${body}\n\n`);
          });
        },
        closeStreams: async () => {
          const pending = responses.map(
            (res) =>
              new Promise<void>((res2) => {
                res.on('close', () => res2());
                res.destroy();
              }),
          );
          responses.length = 0;
          await Promise.all(pending);
          // Give the client a tick to notice the FIN before the next test.
          await new Promise((r) => setTimeout(r, 20));
        },
        close: async () => {
          await new Promise<void>((res2) => server.close(() => res2()));
        },
      });
    });
  });
}

function seededUser(tenantId: string): User {
  return {
    id: 'u1',
    email: 'ta@example.com',
    name: 'Tenant Admin',
    roles: ['TENANT_ADMIN'],
    tenant_id: tenantId,
    is_active: true,
  };
}

const RESET_STATE = {
  user: null,
  active_tenant_id: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

describe('useNotificationStream (SSE-open pins)', () => {
  let server: SseServer;
  let store: typeof import('../../auth/store/authStore');
  let client: typeof import('../../../shared/api/client');
  let hook: typeof import('./useNotificationStream');

  beforeAll(async () => {
    server = await startSseServer();
    vi.stubEnv('VITE_API_BASE_URL', server.baseUrl);
    vi.resetModules();
    // Import AFTER the env stub so the fresh ApiClient reads the real
    // test server as its base URL (the configuration seam).
    store = await import('../../auth/store/authStore');
    client = await import('../../../shared/api/client');
    hook = await import('./useNotificationStream');
  });

  afterAll(async () => {
    vi.unstubAllEnvs();
    vi.resetModules();
    await server.close();
  });

  beforeEach(() => {
    localStorage.clear();
    store.useAuthStore.setState({ ...RESET_STATE });
    client.apiClient.clearTokens();
    client.apiClient.setTenantIdGetter(null);
    client.apiClient._cookieAuthMode = false;
  });

  afterEach(async () => {
    // Unmount FIRST: the hook's cleanup closes its reader, so no
    // reconnect can race the socket teardown below.
    cleanup();
    await server.closeStreams();
    localStorage.clear();
    store.useAuthStore.setState({ ...RESET_STATE });
    client.apiClient.clearTokens();
    client.apiClient.setTenantIdGetter(null);
  });

  it('opens the stream for the active tenant (SSE-open pin)', async () => {
    store.useAuthStore.setState({
      user: seededUser('tenant-sse-1'),
      isAuthenticated: true,
    });
    const qc = new QueryClient();
    const { result } = renderHook(() => hook.useNotificationStream(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    });

    const req = await server.nextStreamRequest();
    expect(req.tenantId).toBe('tenant-sse-1');
    await waitFor(() => expect(result.current.connected).toBe(true));
  });

  it('attaches the operator bearer in token mode (no more 401 storm)', async () => {
    store.useAuthStore.setState({
      user: seededUser('tenant-sse-1'),
      isAuthenticated: true,
    });
    client.apiClient.setAccessToken('header.payload.sig');
    const qc = new QueryClient();
    renderHook(() => hook.useNotificationStream(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    });

    const req = await server.nextStreamRequest();
    expect(req.authorization).toBe('Bearer header.payload.sig');
  });

  it('invalidates the notifications cache when the server pushes notification.created', async () => {
    store.useAuthStore.setState({
      user: seededUser('tenant-sse-1'),
      isAuthenticated: true,
    });
    const qc = new QueryClient();
    qc.setQueryData(['notifications', 'unread-count'], { count: 3 });
    const { result } = renderHook(() => hook.useNotificationStream(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    });

    await server.nextStreamRequest();
    // The stream must be OPEN before the push — the push races the
    // client's header processing otherwise.
    await waitFor(() => expect(result.current.connected).toBe(true));
    server.pushEvent('notification.created', {
      event_type: 'notification.created',
      user_id: 'u1',
    });
    await waitFor(() =>
      expect(qc.getQueryState(['notifications', 'unread-count'])?.isInvalidated).toBe(
        true,
      ),
    );
  });

  it('re-subscribes when the active tenant changes and never reconnects the old stream', async () => {
    store.useAuthStore.setState({
      user: seededUser('tenant-sse-1'),
      isAuthenticated: true,
    });
    const qc = new QueryClient();
    const { result } = renderHook(() => hook.useNotificationStream(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    });

    const first = await server.nextStreamRequest();
    expect(first.tenantId).toBe('tenant-sse-1');
    await waitFor(() => expect(result.current.connected).toBe(true));

    act(() => {
      store.useAuthStore.getState().setActiveTenant('tenant-sse-2');
    });

    const second = await server.nextStreamRequest();
    expect(second.tenantId).toBe('tenant-sse-2');
    await waitFor(() => expect(result.current.connected).toBe(true));
    // The old tenant's reader must not reconnect: beyond the two
    // expected connections, nothing else may arrive (the closed-flag
    // fix — a stale-tenant reconnect would land here).
    await new Promise((r) => setTimeout(r, 1600));
    expect(server.requests.length).toBe(0);
  });

  it('closes the stream on unmount (no reconnect leaks)', async () => {
    store.useAuthStore.setState({
      user: seededUser('tenant-sse-1'),
      isAuthenticated: true,
    });
    const qc = new QueryClient();
    const { result, unmount } = renderHook(() => hook.useNotificationStream(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    });

    await server.nextStreamRequest();
    await waitFor(() => expect(result.current.connected).toBe(true));
    const requestsAtUnmount = server.requests.length;
    unmount();
    // The contract: the cleanup cancels the reconnect timer AND the
    // deliberate close can't schedule a new one (the closed-flag fix).
    // A leaked reconnect would open a NEW stream within the first
    // retry delay (~1s).
    await new Promise((r) => setTimeout(r, 1600));
    expect(server.requests.length).toBe(requestsAtUnmount);
  });

  it('stays silent until the active tenant is known (polling fallback owns freshness)', async () => {
    // No user, no tenant, no token — the stream must not open.
    const qc = new QueryClient();
    const { result } = renderHook(() => hook.useNotificationStream(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    });
    expect(result.current.connected).toBe(false);
    await new Promise((r) => setTimeout(r, 50));
    expect(server.requests.length).toBe(0);
  });
});
