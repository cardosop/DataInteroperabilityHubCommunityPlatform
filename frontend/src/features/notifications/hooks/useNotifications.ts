/**
 * Notification React Query hooks (Phase 223.1).
 *
 * Cache keys are namespaced under `['notifications', ...]` so the
 * WebSocket subscriber can invalidate the whole tree on a server push
 * without knowing the exact filter variants in flight.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useAuthStore } from '../../auth/store/authStore';
import { websocketClient } from '../../../shared/services/websocketClient';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { getErrorMessage } from '../../../shared/utils/errorUtils';
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
  // W5.4 (MEDIUM-8) — mark-read failures were silent: the bell stayed
  // unread with no explanation. The wrapper surfaces them.
  return useMutationWithNotification({
    mutationFn: (id: string) => notificationService.markRead(id),
    errorMessage: (error) => `Couldn't mark notification read: ${getErrorMessage(error)}`,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutationWithNotification({
    mutationFn: () => notificationService.markAllRead(),
    errorMessage: (error) => `Couldn't mark all notifications read: ${getErrorMessage(error)}`,
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

// W5.3 (R2-F3) — the duplicated Phase 228.F3.16 `useNotificationStream`
// (hardcoded URL, no tenant gate, close-on-first-error) was CONSOLIDATED
// into hooks/useNotificationStream.ts — the single SSE hook. Import it
// from there.
