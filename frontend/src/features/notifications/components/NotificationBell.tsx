/**
 * NotificationBell — header bell icon with unread-count badge.
 *
 * Clicking the bell toggles `<NotificationDropdown>`. A `useRef` outside
 * click handler dismisses the dropdown. The badge is hidden when the
 * count is 0 and capped at `99+` to keep the header compact.
 */

import { Bell } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
  useNotificationRealtimeSync,
  useUnreadNotificationCount,
} from '../hooks/useNotifications';
import { NotificationDropdown } from './NotificationDropdown';
import './NotificationBell.css';

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { data: unreadCount = 0 } = useUnreadNotificationCount();
  useNotificationRealtimeSync();

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const label =
    unreadCount > 0
      ? `Notifications, ${unreadCount} unread`
      : 'Notifications';

  return (
    <div className="notification-bell" ref={wrapperRef}>
      <button
        type="button"
        className="notification-bell-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-label={label}
        aria-haspopup="true"
        aria-expanded={open}
        data-testid="notification-bell"
      >
        <Bell size={18} aria-hidden="true" focusable="false" />
        {unreadCount > 0 && (
          <span
            className="notification-bell-badge"
            data-testid="notification-bell-badge"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>
      {open && <NotificationDropdown onClose={() => setOpen(false)} />}
    </div>
  );
}
