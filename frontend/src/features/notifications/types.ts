/**
 * Notification inbox types (Phase 223.1).
 */

export type NotificationType = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';

export type NotificationCategory =
  | 'GOVERNANCE'
  | 'MARKETPLACE'
  | 'JOBS'
  | 'CONTRACTS'
  | 'SYSTEM'
  // Phase 228.F3.5 (REQ-LIN-F3-006) — lineage-driven change-impact
  // notifications.  Backend emits this from the LineageImpactDispatcher
  // when a subscriber's source contract changes above their threshold.
  | 'LINEAGE_IMPACT';

export interface UserNotification {
  id: string;
  tenant: string;
  user: string;
  audit_event?: string | null;
  title: string;
  message: string;
  notification_type: NotificationType;
  category: NotificationCategory;
  resource_type?: string | null;
  resource_id?: string | null;
  read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface UserNotificationListResponse {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: UserNotification[];
}

export interface UserNotificationListFilters {
  page?: number;
  page_size?: number;
  read?: boolean;
  category?: NotificationCategory;
}
