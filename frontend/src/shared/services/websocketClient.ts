/**
 * WebSocket Client
 * For real-time event updates via /ws/events/
 *
 * Backend serves WebSocket at root path /ws/events/ (ASGI), not under /api/v1.
 * We use the origin of the API URL (protocol + host + port) for WS, then append /ws/events/.
 *
 * When the server does not support WebSocket (e.g. 404 from HTTP-only runserver),
 * we treat it as "WS unavailable": stop reconnection and rely on polling. Set
 * VITE_WS_ENABLED=false to skip connecting entirely (e.g. in E2E).
 */

import { apiClient } from '../api/client';

const WS_ENABLED = import.meta.env.VITE_WS_ENABLED !== 'false';

function getWsBaseUrl(): string {
  const explicit = import.meta.env.VITE_WS_BASE_URL;
  if (explicit) return explicit;
  const apiBase = import.meta.env.VITE_API_BASE_URL;
  if (apiBase) {
    try {
      const u = new URL(apiBase);
      const protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${u.host}`;
    } catch {
      return apiBase.replace('http://', 'ws://').replace('https://', 'wss://').replace(/\/api\/v1.*$/, '');
    }
  }
  // No explicit URL configured (nginx-proxied deployment): derive from page origin so
  // the WebSocket connection goes through nginx's /ws proxy rule.
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}`;
  }
  // Non-browser context (SSR): derive from empty string so no hardcoded URL leaks into the bundle
  return '';
}

const WS_BASE_URL = getWsBaseUrl();

export type WebSocketMessageType = 'authenticate' | 'auth_confirmed' | 'subscribe' | 'unsubscribe' | 'list_subscriptions' | 'ping' | 'pong' | 'event';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data?: unknown;
  id?: string;
}

export interface SubscribeMessage {
  event_types: string[];
  filters?: Record<string, unknown>;
}

export interface EventMessage {
  event_type: string;
  data: unknown;
  timestamp: string;
  correlation_id?: string;
}

type EventHandler = (event: EventMessage) => void;
type ErrorHandler = (error: Event) => void;
type CloseHandler = () => void;

/** Close codes that indicate the server does not support WS or rejected the
 * handshake as a POLICY matter (protocol error, policy violation, internal
 * error). 1006 (abnormal closure) is deliberately NOT here: browsers report
 * 1006 both for a failed upgrade AND for a dropped network connection — a
 * single network blip must not permanently disable WS for the session. */
const WS_UNAVAILABLE_CLOSE_CODES = new Set([1002, 1008, 1011]);

interface ActiveSubscription {
  eventTypes: string[];
  filters?: Record<string, unknown>;
}

/** Deterministic key for a subscription (order-insensitive). */
function subscriptionKey(eventTypes: string[]): string {
  return eventTypes.slice().sort().join('|');
}

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private accessToken: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private reconnectTimer: number | null = null;
  private pingInterval: number | null = null;
  private eventHandlers: Map<string, Set<EventHandler>> = new Map();
  private errorHandlers: Set<ErrorHandler> = new Set();
  private closeHandlers: Set<CloseHandler> = new Set();
  /**
   * Every requested subscription (keyed, order-insensitive). Entries stay
   * registered whether or not the socket is OPEN — subscriptions issued at
   * mount (MEDIUM-3) queue here and flush once the connection authenticates;
   * reconnects re-flush the whole set, filters included.
   */
  private subscriptions: Map<string, ActiveSubscription> = new Map();
  private isConnecting = false;
  /** When true, server rejected or doesn't support WS; no reconnect, polling is used. */
  private wsUnavailable = false;
  /** Set by disconnect() so the close event it triggers never schedules a reconnect. */
  private manuallyDisconnected = false;
  /** True once server has confirmed authentication via auth_confirmed. */
  private authenticated = false;
  /** Resolves when the server confirms authentication via auth_confirmed message. */
  private authResolve: (() => void) | null = null;
  private authReject: ((err: Error) => void) | null = null;

  constructor() {
    this.url = `${WS_BASE_URL}/ws/events/`;
  }

  /**
   * Connect to WebSocket server.
   *
   * Opens the connection **without** a token in the URL, then sends an
   * ``authenticate`` message as the first frame. The returned promise
   * resolves once the server replies with ``auth_confirmed``.
   */
  connect(accessToken: string): Promise<void> {
    if (!WS_ENABLED || this.wsUnavailable) {
      return Promise.resolve();
    }
    if (this.ws?.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    this.manuallyDisconnected = false;

    if (this.isConnecting) {
      return new Promise((resolve, reject) => {
        const checkConnection = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN && !this.authResolve) {
            clearInterval(checkConnection);
            resolve();
          } else if (!this.isConnecting) {
            clearInterval(checkConnection);
            reject(new Error('Connection failed'));
          }
        }, 100);
      });
    }

    this.accessToken = accessToken;
    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      try {
        // Connect WITHOUT token in URL (message-based auth)
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          // Send authenticate message as the first frame
          this.authResolve = () => {
            this.authenticated = true;
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            this.startPingInterval();

            // Flush every registered subscription (MEDIUM-3): mount-time
            // subscriptions queued before OPEN/authenticated, plus
            // re-subscriptions after a reconnect — filters preserved.
            this.flushSubscriptions();

            resolve();
          };
          this.authReject = (err: Error) => {
            this.isConnecting = false;
            reject(err);
          };

          const authMessage: WebSocketMessage = {
            type: 'authenticate',
            data: { token: accessToken },
          };
          this.ws!.send(JSON.stringify(authMessage));
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as WebSocketMessage;
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          this.isConnecting = false;
          if (this.authReject) {
            this.authReject(new Error('WebSocket error during authentication'));
            this.authResolve = null;
            this.authReject = null;
          }
          this.errorHandlers.forEach(handler => handler(error));
          reject(error);
        };

        this.ws.onclose = (event) => {
          this.isConnecting = false;
          this.stopPingInterval();
          if (this.authReject) {
            this.authReject(new Error(`WebSocket closed before auth (code ${event.code})`));
            this.authResolve = null;
            this.authReject = null;
          }
          this.closeHandlers.forEach(handler => handler());
          // Intentional close (logout / unmount): never schedule a reconnect —
          // the close event a disconnect() triggers must not resurrect the socket.
          if (this.manuallyDisconnected) {
            return;
          }
          if (WS_UNAVAILABLE_CLOSE_CODES.has(event.code)) {
            this.wsUnavailable = true;
            return;
          }
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          }
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    // Mark FIRST: the close event below fires synchronously on some
    // transports and must not schedule a reconnect after an intentional
    // disconnect (logout / provider unmount).
    this.manuallyDisconnected = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopPingInterval();
    // Clean up pending auth callbacks before closing
    if (this.authReject) {
      this.authReject(new Error('Disconnect called during authentication'));
    }
    this.authResolve = null;
    this.authReject = null;
    this.authenticated = false;
    this.isConnecting = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.subscriptions.clear();
    // The reconnect credential dies with the session — a later connect()
    // supplies the fresh one.
    this.accessToken = null;
    this.reconnectAttempts = 0;
    this.wsUnavailable = false;
  }

  /**
   * Keep the reconnect credential fresh (R2-F5).
   *
   * Wired to ``apiClient``'s token-change registry at module load, so every
   * access-token rotation (login, single-flight refresh, cross-tab sync,
   * logout) updates the token a future reconnect authenticates with —
   * reconnects never re-authenticate with the token captured at first
   * connect.
   */
  updateAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  /**
   * Subscribe to event types.
   *
   * MEDIUM-3: a subscription issued before the socket reached OPEN +
   * authenticated was dropped (console-warn + return) — mount-time
   * subscriptions lost for the whole session. Subscriptions are now
   * ALWAYS registered; when the socket is not ready they queue and flush
   * once the connection authenticates (and again on every reconnect).
   */
  subscribe(eventTypes: string[], filters?: Record<string, unknown>): void {
    this.subscriptions.set(subscriptionKey(eventTypes), { eventTypes, filters });

    if (this.ws?.readyState === WebSocket.OPEN && this.authenticated) {
      this.sendMessage({
        type: 'subscribe',
        data: {
          event_types: eventTypes,
          filters,
        } as SubscribeMessage,
      });
    }
    // else: queued — flushSubscriptions() sends it on auth_confirmed.
  }

  /**
   * Unsubscribe from event types (removes any queued copy too).
   */
  unsubscribe(eventTypes: string[]): void {
    this.subscriptions.delete(subscriptionKey(eventTypes));

    if (this.ws?.readyState === WebSocket.OPEN && this.authenticated) {
      this.sendMessage({
        type: 'unsubscribe',
        data: {
          event_types: eventTypes,
        },
      });
    }
  }

  /**
   * Add event handler
   */
  onEvent(eventType: string, handler: EventHandler): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.eventHandlers.get(eventType)?.delete(handler);
    };
  }

  /**
   * Add error handler
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => {
      this.errorHandlers.delete(handler);
    };
  }

  /**
   * Add close handler
   */
  onClose(handler: CloseHandler): () => void {
    this.closeHandlers.add(handler);
    return () => {
      this.closeHandlers.delete(handler);
    };
  }

  /**
   * Send every registered subscription to the server. Runs on
   * auth_confirmed (first connect and every reconnect); queued
   * mount-time subscriptions (MEDIUM-3) flush here with their filters.
   */
  private flushSubscriptions(): void {
    this.subscriptions.forEach(({ eventTypes, filters }) => {
      this.sendMessage({
        type: 'subscribe',
        data: {
          event_types: eventTypes,
          filters,
        } as SubscribeMessage,
      });
    });
  }

  private sendMessage(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private handleMessage(message: WebSocketMessage): void {
    if (message.type === 'auth_confirmed') {
      // Server confirmed message-based authentication
      if (this.authResolve) {
        this.authResolve();
        this.authResolve = null;
        this.authReject = null;
      }
    } else if ((message as { type: string; error?: string }).error && this.authReject) {
      // Server sent an error during auth handshake (e.g. invalid token).
      // Reject the connect() promise so the caller gets a clear error
      // instead of waiting for the close event.
      const errMsg = (message as { error?: string }).error ?? 'Authentication error';
      this.authReject(new Error(errMsg));
      this.authResolve = null;
      this.authReject = null;
    } else if (message.type === 'event') {
      const eventMessage = message.data as EventMessage;
      const handlers = this.eventHandlers.get(eventMessage.event_type);
      if (handlers) {
        handlers.forEach(handler => handler(eventMessage));
      }
    } else if (message.type === 'pong') {
      // Pong received, connection is alive
    }
  }

  private startPingInterval(): void {
    this.stopPingInterval();
    this.pingInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        const message: WebSocketMessage = { type: 'ping' };
        this.ws.send(JSON.stringify(message));
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.wsUnavailable) {
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (this.accessToken && !this.wsUnavailable) {
        this.connect(this.accessToken).catch((err) => {
          // G4.5 (glittery-herding-graham): log reconnect failures instead of
          // silently swallowing them. onclose will set wsUnavailable and stop retries.
          console.warn('WebSocket reconnect failed:', err);
        });
      }
    }, delay);
  }

  /**
   * Get connection status
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN && this.authenticated;
  }
}

export const websocketClient = new WebSocketClient();

// W5.4 (R2-F5) — keep the reconnect credential fresh: every access-token
// change (login, single-flight refresh, cross-tab sync, logout) updates the
// stored token so a reconnect never re-authenticates with a stale credential.
apiClient.onAccessTokenChange((token) => websocketClient.updateAccessToken(token));
