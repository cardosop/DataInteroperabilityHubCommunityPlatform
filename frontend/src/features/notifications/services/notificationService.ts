/**
 * Notification service (Phase 223.1).
 * Thin wrapper over the `/notifications/user-notifications/` REST endpoints.
 */

import { apiClient } from '../../../shared/api/client';
import type {
  UserNotification,
  UserNotificationListFilters,
  UserNotificationListResponse,
} from '../types';

const BASE = 'notifications/user-notifications';

export const notificationService = {
  async list(
    filters: UserNotificationListFilters = {},
  ): Promise<UserNotificationListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    if (filters.read != null) params.set('read', String(filters.read));
    if (filters.category) params.set('category', filters.category);
    const qs = params.toString();
    const url = qs ? `${BASE}/?${qs}` : `${BASE}/`;
    const response = await apiClient
      .getClient()
      .get<UserNotificationListResponse>(url);
    return response.data;
  },

  async unreadCount(): Promise<number> {
    const response = await apiClient
      .getClient()
      .get<{ count: number }>(`${BASE}/unread-count/`);
    return response.data.count;
  },

  async markRead(id: string): Promise<UserNotification> {
    const response = await apiClient
      .getClient()
      .post<UserNotification>(`${BASE}/${id}/read/`, {});
    return response.data;
  },

  async markAllRead(): Promise<number> {
    const response = await apiClient
      .getClient()
      .post<{ updated: number }>(`${BASE}/read-all/`, {});
    return response.data.updated;
  },
};
