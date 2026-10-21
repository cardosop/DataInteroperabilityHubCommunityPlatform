/**
 * Phase 276.B.113 — SSE consumer for /notifications/stream/.
 *
 * Subscribes to server-sent events for real-time notification delivery.
 *
 * W5.3 (R2-F3) — this is the SINGLE stream hook, FETCH-BASED. The pre-fix
 * tree had two divergent browser-EventSource implementations: the mounted
 * one (in useNotifications.ts) hardcoded `/api/v1/...`, carried no tenant
 * gate, and closed on the FIRST error; the other gated on a phantom
 * `accessToken` store field that was never written, so it never opened.
 * Both shared a deeper root cause: the browser's native `EventSource`
 * cannot attach headers AND is unreliable about attaching cookies
 * (`withCredentials` is ignored by current Chromium — measured against
 * the real stack, Chrome 145: the same-origin fetch carried the
 * httpOnly session cookies, the EventSource request carried NO Cookie
 * header and 401'd every connect). A fetch-based reader fixes the
 * credential class at the root AND works identically in every browser:
 *
 * - gates on the FIXED useActiveTenantId (the active tenant — the
 *   stream re-opens when the user switches tenant, and cross-tab
 *   switches re-derive via the storage event),
 * - builds the URL from apiClient.baseURL (a non-default
 *   VITE_API_BASE_URL used to break the hardcoded path),
 * - sends `credentials: 'include'` (cookie-mode sessions) AND the
 *   operator's Bearer token when the client is in token mode (the
 *   pre-fix token-mode stream could never authenticate — the
 *   401-storm class is gone, not just guarded),
 * - invalidates the notifications query cache on every
 *   `notification.created` push (the mounted behavior),
 * - reconnects with capped exponential backoff (server-initiated
 *   close, connection drop, non-2xx — giving up after a few
 *   consecutive failures; the 60s polling fallback owns inbox
 *   freshness otherwise),
 * - a `closed` flag so a deliberate close (tenant switch/unmount) can
 *   never schedule a stale-tenant reconnect.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiClient } from '../../../shared/api/client';
import { useActiveTenantId } from '../../auth/hooks/useActiveTenantId';

/** Max consecutive connection failures before giving up. */
const MAX_RECONNECT_ATTEMPTS = 3;
const INITIAL_RETRY_DELAY_MS = 1000;
const MAX_RETRY_DELAY_MS = 30000;

/** Compose the stream URL from the client's real base URL. */
export function buildNotificationStreamUrl(tenantId: string): string {
  return `${apiClient.baseURL}/notifications/stream/?tenant_id=${encodeURIComponent(tenantId)}`;
}

export function useNotificationStream(): { connected: boolean } {
  const tenantId = useActiveTenantId();
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Never open before the active tenant is known.
    if (!tenantId) {
      setConnected(false);
      return;
    }

    // Deliberate-close guard: cleanup sets this before aborting, so
    // neither the reader loop nor a late error/reconnect path can
    // schedule a stale-tenant reconnect after unmount/switch.
    let closed = false;
    let controller: AbortController | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let retryDelay = INITIAL_RETRY_DELAY_MS;
    let reconnectAttempts = 0;

    /** Parse one SSE frame and act on the events we subscribe to. */
    const handleFrame = (frame: string): void => {
      let eventType = 'message';
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) {
          eventType = line.slice('event:'.length).trim();
        }
        // `data:` lines carry the payload; comment lines (": ping")
        // and anything else are ignored.
      }
      if (eventType === 'notification.created') {
        // Real-time invalidation — the bell + list re-fetch immediately.
        void queryClient.invalidateQueries({ queryKey: ['notifications'] });
      }
    };

    /** Consume the stream body frame-by-frame until it ends or closes. */
    const readStream = async (res: Response): Promise<void> => {
      if (!res.body) throw new Error('stream response has no body');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (closed) return;
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            handleFrame(frame);
            boundary = buffer.indexOf('\n\n');
          }
        }
      } finally {
        reader.releaseLock();
      }
    };

    const scheduleReconnect = (): void => {
      if (closed) return;
      reconnectAttempts += 1;
      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;
      reconnectTimer = setTimeout(() => void connect(), retryDelay);
      retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY_MS);
    };

    const connect = async (): Promise<void> => {
      if (closed) return;
      controller = new AbortController();
      // Credentials mirror the apiClient: cookie-mode sessions ride the
      // httpOnly cookies (credentials: 'include'); token-mode sessions
      // attach the OPERATOR bearer (never the impersonation bearer —
      // the stream follows the credentials the request actually sends).
      const headers: Record<string, string> = { Accept: 'text/event-stream' };
      const token = apiClient.getAccessToken();
      if (token && !apiClient._cookieAuthMode) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      try {
        const res = await fetch(buildNotificationStreamUrl(tenantId), {
          credentials: 'include',
          headers,
          signal: controller.signal,
        });
        if (closed) return;
        if (!res.ok) throw new Error(`stream returned ${res.status}`);
        setConnected(true);
        retryDelay = INITIAL_RETRY_DELAY_MS;
        reconnectAttempts = 0;
        await readStream(res);
        // The server closed the stream (its 30-min ceiling, or the
        // Redis-down early-close) — reconnect with backoff.
        if (closed) return;
        setConnected(false);
        scheduleReconnect();
      } catch {
        if (closed) return;
        setConnected(false);
        scheduleReconnect();
      }
    };

    void connect();

    return () => {
      closed = true;
      if (reconnectTimer !== undefined) clearTimeout(reconnectTimer);
      controller?.abort();
    };
  }, [tenantId, queryClient]);

  return { connected };
}
