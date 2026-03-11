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
  return 'ws://localhost:8000';
}

const WS_BASE_URL = getWsBaseUrl();

export type WebSocketMessageType = 'subscribe' | 'unsubscribe' | 'list_subscriptions' | 'ping' | 'pong' | 'event';

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

/** Close codes that indicate server does not support WS or rejected handshake (e.g. 404). */
const WS_UNAVAILABLE_CLOSE_CODES = new Set([1002, 1006, 1008, 1011]);

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
  private subscribedEventTypes: Set<string> = new Set();
  private isConnecting = false;
  /** When true, server rejected or doesn't support WS; no reconnect, polling is used. */
  private wsUnavailable = false;

  constructor() {
    this.url = `${WS_BASE_URL}/ws/events/`;
  }

  /**
   * Connect to WebSocket server
   */
  connect(accessToken: string): Promise<void> {
    if (!WS_ENABLED || this.wsUnavailable) {
      return Promise.resolve();
    }
    if (this.ws?.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    if (this.isConnecting) {
      return new Promise((resolve, reject) => {
        const checkConnection = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
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
        const wsUrl = `${this.url}?token=${encodeURIComponent(accessToken)}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.startPingInterval();
          
          // Re-subscribe to previously subscribed event types
          if (this.subscribedEventTypes.size > 0) {
            this.subscribe(Array.from(this.subscribedEventTypes));
          }
          
          resolve();
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
          this.errorHandlers.forEach(handler => handler(error));
          reject(error);
        };

        this.ws.onclose = (event) => {
          this.isConnecting = false;
          this.stopPingInterval();
          this.closeHandlers.forEach(handler => handler());
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
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.subscribedEventTypes.clear();
    this.wsUnavailable = false;
  }

  /**
   * Subscribe to event types
   */
  subscribe(eventTypes: string[], filters?: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot subscribe');
      return;
    }

    const message: WebSocketMessage = {
      type: 'subscribe',
      data: {
        event_types: eventTypes,
        filters,
      } as SubscribeMessage,
    };

    eventTypes.forEach(type => this.subscribedEventTypes.add(type));
    this.ws.send(JSON.stringify(message));
  }

  /**
   * Unsubscribe from event types
   */
  unsubscribe(eventTypes: string[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const message: WebSocketMessage = {
      type: 'unsubscribe',
      data: {
        event_types: eventTypes,
      },
    };

    eventTypes.forEach(type => this.subscribedEventTypes.delete(type));
    this.ws.send(JSON.stringify(message));
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

  private handleMessage(message: WebSocketMessage): void {
    if (message.type === 'event') {
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
        this.connect(this.accessToken).catch(() => {
          // Handshake failed (e.g. 404); onclose will set wsUnavailable and stop further retries
        });
      }
    }, delay);
  }

  /**
   * Get connection status
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const websocketClient = new WebSocketClient();
