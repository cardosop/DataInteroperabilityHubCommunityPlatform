/**
 * NotificationListPage — full-page inbox (Phase 223.1).
 */

import { useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from '../hooks/useNotifications';
import type { NotificationCategory } from '../types';
import './NotificationListPage.css';

const CATEGORIES: Array<{ value: NotificationCategory | 'ALL'; label: string }> = [
  { value: 'ALL', label: 'All' },
  { value: 'GOVERNANCE', label: 'Governance' },
  { value: 'MARKETPLACE', label: 'Marketplace' },
  { value: 'JOBS', label: 'Jobs' },
  { value: 'CONTRACTS', label: 'Contracts' },
  { value: 'SYSTEM', label: 'System' },
];

export function NotificationListPage() {
  const [category, setCategory] = useState<NotificationCategory | 'ALL'>('ALL');
  const [page, setPage] = useState(1);
  const filters =
    category === 'ALL'
      ? { page, page_size: 25 }
      : { page, page_size: 25, category };
  const { data, isLoading } = useNotifications(filters);
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  const items = data?.results ?? [];

  return (
    <div className="notification-list-page" data-testid="notification-list-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Notifications' },
        ]}
      />
      <div className="notification-list-header">
        <h1>Notifications</h1>
        <button
          type="button"
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending || items.every((i) => i.read)}
        >
          Mark all as read
        </button>
      </div>

      <div className="notification-list-filters">
        {CATEGORIES.map((c) => (
          <button
            key={c.value}
            type="button"
            className={`notification-list-filter ${category === c.value ? 'active' : ''}`}
            onClick={() => {
              setCategory(c.value);
              setPage(1);
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {isLoading && <LoadingSpinner />}

      <ul className="notification-list" role="list">
        {!isLoading && items.length === 0 && (
          <li className="notification-list-empty">No notifications.</li>
        )}
        {items.map((n) => (
          <li
            key={n.id}
            className={`notification-list-item ${n.read ? '' : 'unread'} notification-${n.notification_type.toLowerCase()}`}
            data-testid={`notification-list-row-${n.id}`}
          >
            <div className="notification-list-item-body">
              <strong>{n.title}</strong>
              <p>{n.message}</p>
              <span className="notification-list-item-meta">
                {new Date(n.created_at).toLocaleString()} · {n.category}
              </span>
            </div>
            {!n.read && (
              <button
                type="button"
                onClick={() => markRead.mutate(n.id)}
                disabled={markRead.isPending}
              >
                Mark as read
              </button>
            )}
          </li>
        ))}
      </ul>

      {data && data.total_pages > 1 && (
        <div className="notification-list-pagination">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span>
            Page {page} of {data.total_pages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={page === data.total_pages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
