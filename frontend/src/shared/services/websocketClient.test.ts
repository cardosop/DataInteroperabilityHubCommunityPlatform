/**
 * WebSocketClient contract pins — W5.4 (R2-F5).
 *
 * MEDIUM-3: subscriptions issued at component mount (before the socket
 * reaches OPEN + auth_confirmed) were DROPPED — a mount-race that left
 * realtime dead for the whole session. Subscriptions must queue and
 * flush once the connection authenticates.
 *
 * R2-F5 also pins: reconnect re-subscribes WITH filters, reconnect
 * authenticates with the CURRENT token (not the one captured at first
 * connect), an intentional disconnect never schedules a reconnect, and
 * a network-drop close (1006) does not permanently disable WS.
 *
 * jsdom ships no WebSocket — the fake below is a browser-primitive
 * harness seam (the same way jsdom fakes the DOM). The unit under test
 * is the real singleton, the real apiClient listener registry, and real
 * timers.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/** Minimal browser-faithful WebSocket primitive for jsdom. */
class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  static reset(): void {
    FakeWebSocket.instances.length = 0;
  }

  readyState = FakeWebSocket.CONNECTING;
  url: string;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev?: unknown) => void) | null = null;
  onclose: ((ev: { code?: number; reason?: string }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  serverOpen(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  serverMessage(message: unknown): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  serverClose(code: number): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code });
  }

  send(data: string): void {
    if (this.readyState !== FakeWebSocket.OPEN) {
      throw new Error('send() on non-OPEN socket');
    }
    this.sent.push(data);
  }

  close(code = 1000): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code });
  }
}

vi.stubGlobal('WebSocket', FakeWebSocket);

import { websocketClient } from './websocketClient';
import { apiClient } from '../api/client';

interface SentMessage {
  type: string;
  data?: unknown;
}

function sentMessages(socket: FakeWebSocket): SentMessage[] {
  return socket.sent.map((raw) => JSON.parse(raw) as SentMessage);
}

function sentTypes(socket: FakeWebSocket): string[] {
  return sentMessages(socket).map((m) => m.type);
}

async function connectAndAuthenticate(token: string): Promise<FakeWebSocket> {
  const connectPromise = websocketClient.connect(token);
  const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  socket.serverOpen();
  socket.serverMessage({ type: 'auth_confirmed' });
  await connectPromise;
  return socket;
}

describe('websocketClient subscription queue (MEDIUM-3)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    websocketClient.disconnect();
    apiClient.setAccessToken(null);
    FakeWebSocket.reset();
  });

  afterEach(() => {
    websocketClient.disconnect();
    vi.useRealTimers();
  });

  it('queues a subscribe issued BEFORE connect and flushes it after auth', async () => {
    // Mount race: the hook subscribes while the AppProviders connect has
    // not even started (no socket exists yet).
    websocketClient.subscribe(['notification.created'], { tenant_id: 't1' });

    const socket = await connectAndAuthenticate('token-a');

    const types = sentTypes(socket);
    expect(types[0]).toBe('authenticate');
    expect(types).toContain('subscribe');
    const subscribe = sentMessages(socket).find((m) => m.type === 'subscribe');
    expect(subscribe?.data).toEqual({
      event_types: ['notification.created'],
      filters: { tenant_id: 't1' },
    });
  });

  it('queues a subscribe issued while CONNECTING and flushes it after auth', async () => {
    const connectPromise = websocketClient.connect('token-a');
    const socket = FakeWebSocket.instances[0];

    // Socket exists but is still CONNECTING (0) — pre-fix this drops.
    websocketClient.subscribe(['notification.read']);

    socket.serverOpen();
    socket.serverMessage({ type: 'auth_confirmed' });
    await connectPromise;

    const subscribe = sentMessages(socket).find((m) => m.type === 'subscribe');
    expect(subscribe?.data).toEqual({
      event_types: ['notification.read'],
      filters: undefined,
    });
  });

  it('sends immediately when already open and authenticated (regression pin)', async () => {
    const socket = await connectAndAuthenticate('token-a');

    websocketClient.subscribe(['contract.updated']);

    expect(sentTypes(socket)).toEqual(['authenticate', 'subscribe']);
  });

  it('removes a queued subscription when unsubscribed before the flush', async () => {
    websocketClient.subscribe(['notification.created']);
    websocketClient.unsubscribe(['notification.created']);

    const socket = await connectAndAuthenticate('token-a');

    expect(sentTypes(socket)).not.toContain('subscribe');
  });

  it('re-subscribes with FILTERS after a reconnect (filters survive)', async () => {
    const first = await connectAndAuthenticate('token-a');
    websocketClient.subscribe(['notification.created'], { tenant_id: 't1' });
    first.serverClose(1000); // normal server close → reconnect

    await vi.advanceTimersByTimeAsync(1100);
    const second = FakeWebSocket.instances[1];
    second.serverOpen();
    second.serverMessage({ type: 'auth_confirmed' });

    const subscribe = sentMessages(second).find((m) => m.type === 'subscribe');
    expect(subscribe?.data).toEqual({
      event_types: ['notification.created'],
      filters: { tenant_id: 't1' },
    });
  });
});

describe('websocketClient token freshness (R2-F5 reconnect)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    websocketClient.disconnect();
    apiClient.setAccessToken(null);
    FakeWebSocket.reset();
  });

  afterEach(() => {
    websocketClient.disconnect();
    vi.useRealTimers();
  });

  it('reconnects with the CURRENT token after a refresh, not the stale one', async () => {
    await connectAndAuthenticate('token-a');
    const first = FakeWebSocket.instances[0];
    first.serverClose(1000);

    // The API client rotates the token (single-flight refresh path).
    apiClient.setAccessToken('token-b');

    await vi.advanceTimersByTimeAsync(1100);
    const second = FakeWebSocket.instances[1];
    expect(second).toBeDefined();
    second.serverOpen();

    const auth = sentMessages(second).find((m) => m.type === 'authenticate');
    expect(auth?.data).toEqual({ token: 'token-b' });
  });

  it('does NOT reconnect after an intentional disconnect (logout) even with a token present', async () => {
    await connectAndAuthenticate('token-a');

    websocketClient.disconnect();

    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeWebSocket.instances.length).toBe(1);
  });

  it('treats a network-drop close (1006) as reconnectable, not WS-unavailable', async () => {
    await connectAndAuthenticate('token-a');
    const first = FakeWebSocket.instances[0];

    first.serverClose(1006); // abnormal closure — network blip, not a policy refusal

    await vi.advanceTimersByTimeAsync(1100);
    expect(FakeWebSocket.instances.length).toBe(2);
  });

  it('keeps a policy close (1008) as permanently unavailable (regression pin)', async () => {
    await connectAndAuthenticate('token-a');
    const first = FakeWebSocket.instances[0];

    first.serverClose(1008);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});

describe('apiClient access-token change registry', () => {
  beforeEach(() => {
    websocketClient.disconnect();
    apiClient.setAccessToken(null);
  });

  afterEach(() => {
    websocketClient.disconnect();
    vi.useRealTimers();
  });

  it('notifies subscribers on token change and supports unsubscription', () => {
    const seen: Array<string | null> = [];
    const unsubscribe = apiClient.onAccessTokenChange((token) => seen.push(token));

    apiClient.setAccessToken('t1');
    apiClient.setAccessToken('t1'); // same value — no redundant notification
    apiClient.setAccessToken(null);

    expect(seen).toEqual(['t1', null]);

    unsubscribe();
    apiClient.setAccessToken('t2');
    expect(seen).toEqual(['t1', null]);
  });

  it('keeps the websocket client token fresh through the production registry wiring', async () => {
    // The production wiring: apiClient's registry listener feeds the WS
    // client's stored token — no mock of either module. Proven through the
    // reconnect path: after a token rotation, the reconnect authenticates
    // with the rotated token.
    vi.useFakeTimers();
    await connectAndAuthenticate('old-token');
    const first = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
    first.serverClose(1000);

    apiClient.setAccessToken('fresh-token');

    await vi.advanceTimersByTimeAsync(1100);
    const second = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
    expect(second).not.toBe(first);
    second.serverOpen();

    const auth = sentMessages(second).find((m) => m.type === 'authenticate');
    expect(auth?.data).toEqual({ token: 'fresh-token' });

    // Complete the handshake so the teardown disconnect has nothing to reject.
    second.serverMessage({ type: 'auth_confirmed' });
    vi.useRealTimers();
  });
});
