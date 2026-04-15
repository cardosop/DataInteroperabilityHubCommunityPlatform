/**
 * NotificationDropdown — recent notifications list under the bell.
 *
 * Shows up to 10 latest notifications; clicking a row marks it read and
 * navigates to the linked resource (when we can derive a route). "Mark
 * all as read" and "View all" links let the user reach the full list
 * page.
 */

import { Link, useNavigate } from 'react-router-dom';
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from '../hooks/useNotifications';
import type { UserNotification } from '../types';
import './NotificationDropdown.css';

export interface NotificationDropdownProps {
  onClose: () => void;
}

/** Map a notification's resource_type/_id to a SPA route, if we have one. */
function resolveRoute(n: UserNotification): string | null {
  if (!n.resource_type || !n.resource_id) return null;
  switch (n.resource_type) {
    case 'ACCESS_REQUEST':
      return `/governance/access-requests/${n.resource_id}`;
    case 'ORDER':
      return `/marketplace/orders/${n.resource_id}`;
    case 'JOB':
      return `/jobs/${n.resource_id}`;
    case 'CONTRACT':
      return `/contracts/${n.resource_id}`;
    case 'ASSET':
      return `/assets/${n.resource_id}`;
    default:
      return null;
  }
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function NotificationDropdown({ onClose }: NotificationDropdownProps) {
  const navigate = useNavigate();
  const { data, isLoading } = useNotifications({ page: 1, page_size: 10 });
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  const items = data?.results ?? [];

  const handleRowClick = async (n: UserNotification) => {
    if (!n.read) {
      try {
        await markRead.mutateAsync(n.id);
      } catch {
        /* silent — next list fetch resyncs */
      }
    }
    const route = resolveRoute(n);
    onClose();
    if (route) navigate(route);
  };

  return (
    <div
      className="notification-dropdown"
      role="dialog"
      aria-label="Notifications"
      data-testid="notification-dropdown"
    >
      <header className="notification-dropdown-header">
        <span className="notification-dropdown-title">Notifications</span>
        <button
          type="button"
          className="notification-dropdown-mark-all"
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending || items.every((i) => i.read)}
          data-testid="notification-mark-all-read"
        >
          Mark all as read
        </button>
      </header>

      <ul className="notification-dropdown-list" role="list">
        {isLoading && (
          <li className="notification-dropdown-empty">Loading…</li>
        )}
        {!isLoading && items.length === 0 && (
          <li className="notification-dropdown-empty">You're all caught up.</li>
        )}
        {items.map((n) => (
          <li
            key={n.id}
            className={`notification-dropdown-item notification-${n.notification_type.toLowerCase()} ${
              n.read ? '' : 'unread'
            }`}
            data-testid={`notification-row-${n.id}`}
          >
            <button
              type="button"
              className="notification-dropdown-row"
              onClick={() => handleRowClick(n)}
            >
              <span className="notification-dropdown-row-title">{n.title}</span>
              <span className="notification-dropdown-row-message">
                {n.message}
              </span>
              <span className="notification-dropdown-row-meta">
                {formatRelative(n.created_at)} · {n.category}
              </span>
            </button>
          </li>
        ))}
      </ul>

      <footer className="notification-dropdown-footer">
        <Link to="/notifications" onClick={onClose}>
          View all
        </Link>
      </footer>
    </div>
  );
}
