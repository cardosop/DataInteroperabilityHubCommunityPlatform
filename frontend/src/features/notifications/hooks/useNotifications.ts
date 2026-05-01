/**
 * Notification React Query hooks (Phase 223.1).
 *
 * Cache keys are namespaced under `['notifications', ...]` so the
 * WebSocket subscriber can invalidate the whole tree on a server push
 * without knowing the exact filter variants in flight.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useAuthStore } from '../../auth/store/authStore';
import { websocketClient } from '../../../shared/services/websocketClient';
import { notificationService } from '../services/notificationService';
import type { UserNotificationListFilters } from '../types';

const QK = {
  list: (f: UserNotificationListFilters) =>
    ['notifications', 'list', f] as const,
  unread: ['notifications', 'unread-count'] as const,
};

export function useNotifications(filters: UserNotificationListFilters = {}) {
  return useQuery({
    queryKey: QK.list(filters),
    queryFn: () => notificationService.list(filters),
  });
}

export function useUnreadNotificationCount() {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: QK.unread,
    queryFn: () => notificationService.unreadCount(),
    enabled: !!user,
    // Poll every 60s as a fallback; the WS subscriber below invalidates
    // this key in real-time when the server pushes a notification event.
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationService.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => notificationService.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

/**
 * Subscribe to server-pushed `notification.*` events and invalidate
 * the React Query cache so the bell + list re-fetch immediately.
 *
 * Mounted once at the Header level so every page sees live updates.
 */
export function useNotificationRealtimeSync(): void {
  const qc = useQueryClient();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (!user) return;
    const eventTypes = ['notification.created', 'notification.read'];
    try {
      websocketClient.subscribe(eventTypes);
    } catch {
      /* WS may not be connected yet; onEvent will still attach. */
    }
    const unsubscribers = eventTypes.map((t) =>
      websocketClient.onEvent(t, () => {
        qc.invalidateQueries({ queryKey: ['notifications'] });
      }),
    );
    return () => {
      unsubscribers.forEach((fn) => fn());
      try {
        websocketClient.unsubscribe(eventTypes);
      } catch {
        /* ignore — may already be disconnected */
      }
    };
  }, [qc, user]);
}

/**
 * Phase 228.F3.16 — SSE-backed notification stream with polling
 * fallback.
 *
 * The hook opens an `EventSource` to `/api/v1/notifications/stream/`.
 * On every `notification.created` SSE event, the React Query
 * `notifications` cache is invalidated so the bell + list re-fetch.
 *
 * Failure mode: if the browser's `EventSource` constructor throws
 * (no SSE support or proxy strips it), or the stream errors before
 * the first event, the hook bails — the existing 60-second polling
 * (`useUnreadNotificationCount`) continues to refresh the inbox.
 */
export function useNotificationStream(): void {
  const qc = useQueryClient();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (!user) return;
    if (typeof EventSource === 'undefined') return;

    let source: EventSource | null = null;
    try {
      source = new EventSource('/api/v1/notifications/stream/', {
        withCredentials: true,
      });
    } catch {
      return;
    }

    const handler = () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    };
    source.addEventListener('notification.created', handler);
    source.addEventListener('error', () => {
      // Let the browser retry; if it can't, polling fallback covers us.
    });

    return () => {
      source?.removeEventListener('notification.created', handler);
      source?.close();
    };
  }, [qc, user]);
}
