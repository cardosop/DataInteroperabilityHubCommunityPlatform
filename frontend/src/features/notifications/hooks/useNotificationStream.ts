/**
 * Phase 276.B.113 — SSE consumer for /notifications/stream/.
 *
 * Subscribes to server-sent events for real-time notification delivery.
 * Auto-reconnects on connection loss with exponential backoff.
 */
import { useEffect, useState } from 'react';
import { useActiveTenantId } from '../../auth/hooks/useActiveTenantId';

interface StreamEvent {
  id: string;
  type: string;
  data: Record<string, unknown>;
}

export function useNotificationStream() {
  const tenantId = useActiveTenantId();
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!tenantId) return;

    let retryDelay = 1000;
    let reconnectAttempts = 0;
    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      eventSource = new EventSource(
        `/api/v1/notifications/stream/?tenant_id=${tenantId}`,
      );

      eventSource.onopen = () => {
        setConnected(true);
        retryDelay = 1000;
        reconnectAttempts = 0;
      };

      eventSource.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data);
          setEvents((prev) => [...prev.slice(-99), parsed]);
        } catch {
          // Ignore malformed events.
        }
      };

      eventSource.onerror = () => {
        setConnected(false);
        eventSource?.close();
        reconnectAttempts += 1;
        // EventSource cannot attach the Bearer token, so in token-auth mode
        // every connect 401s and this loop would retry forever (1s→30s
        // backoff, hundreds of 401s per session). Give up after a few
        // consecutive failures and let the 60s polling fallback own inbox
        // freshness. A working cookie-auth stream resets the counter on open.
        if (reconnectAttempts >= 3) return;
        reconnectTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      };
    };

    connect();

    return () => {
      eventSource?.close();
      clearTimeout(reconnectTimer);
    };
  }, [tenantId]);

  return { events, connected };
}
