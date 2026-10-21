/**
 * Admin Service
 * API client for admin operations (tenants, users)
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  PlatformTenantUsageResponse,
  Tenant,
  TenantConfig,
  TenantListFilters,
} from '../../../shared/types/tenants';
import type { User, UserListFilters } from '../../../shared/types/users';

const TENANTS_BASE_PATH = 'tenants';
const PLATFORM_TENANTS_BASE_PATH = 'platform/tenants';
const USERS_BASE_PATH = 'users';

export const adminService = {
  /**
   * List tenants (Platform Admin only)
   */
  async listTenants(filters: TenantListFilters = {}): Promise<PaginatedResponse<Tenant>> {
    const params = new URLSearchParams();
    if (filters.page) params.set('page', String(filters.page));
    if (filters.page_size) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const url = qs ? `${TENANTS_BASE_PATH}/?${qs}` : `${TENANTS_BASE_PATH}/`;
    const response = await apiClient.getClient().get<PaginatedResponse<Tenant>>(url);
    return response.data;
  },

  /**
   * Get tenant by ID
   */
  async getTenant(id: string): Promise<Tenant> {
    const response = await apiClient.getClient().get<Tenant>(`${TENANTS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new organization tenant (Platform Admin only).
   * POST /api/v1/tenants/
   */
  async createTenant(data: { name: string; slug: string; region?: string }): Promise<Tenant> {
    const response = await apiClient.getClient().post<Tenant>(`${TENANTS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Suspend a tenant (Platform Admin only).
   * POST /api/v1/tenants/{id}/suspend/
   */
  async suspendTenant(id: string, reason?: string): Promise<Tenant> {
    const response = await apiClient
      .getClient()
      .post<Tenant>(`${TENANTS_BASE_PATH}/${id}/suspend/`, reason != null ? { reason } : {});
    return response.data;
  },

  /**
   * Resume (reactivate) a suspended tenant (Platform Admin only).
   * POST /api/v1/tenants/{id}/reactivate/
   */
  async resumeTenant(id: string): Promise<Tenant> {
    const response = await apiClient
      .getClient()
      .post<Tenant>(`${TENANTS_BASE_PATH}/${id}/reactivate/`, {});
    return response.data;
  },

  /**
   * Get usage summary for all tenants (Platform Admin only).
   * GET /api/v1/platform/tenants/usage/
   */
  async getPlatformTenantUsage(): Promise<PlatformTenantUsageResponse> {
    const response = await apiClient
      .getClient()
      .get<PlatformTenantUsageResponse>(`${PLATFORM_TENANTS_BASE_PATH}/usage/`);
    return response.data;
  },

  /**
   * Get tenant configuration
   */
  async getTenantConfig(tenantId: string): Promise<TenantConfig> {
    const response = await apiClient
      .getClient()
      .get<TenantConfig>(`${TENANTS_BASE_PATH}/${tenantId}/config/`);
    return response.data;
  },

  /**
   * List users (tenant-scoped or all for platform admin)
   */
  async listUsers(filters: UserListFilters = {}): Promise<PaginatedResponse<User>> {
    const params = new URLSearchParams();
    if (filters.page) params.set('page', String(filters.page));
    if (filters.page_size) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const url = qs ? `${USERS_BASE_PATH}/?${qs}` : `${USERS_BASE_PATH}/`;
    const response = await apiClient.getClient().get<PaginatedResponse<User>>(url);
    return response.data;
  },

  /**
   * Get user by ID
   */
  async getUser(id: string): Promise<User> {
    const response = await apiClient.getClient().get<User>(`${USERS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Update user (roles, status, display_name). Requires TENANT_ADMIN or PLATFORM_ADMIN.
   */
  async updateUser(
    id: string,
    data: { display_name?: string; status?: string; role_ids?: string[] }
  ): Promise<User> {
    const response = await apiClient.getClient().put<User>(`${USERS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * List roles (tenant-scoped or all for platform admin)
   */
  async listRoles(): Promise<{ id: string; tenant: string; name: string; description?: string }[]> {
    const response = await apiClient
      .getClient()
      .get<
        PaginatedResponse<{ id: string; tenant: string; name: string; description?: string }>
      >(`${USERS_BASE_PATH}/roles/?page_size=100`);
    return response.data.results ?? [];
  },

  // ── Feature flags ──────────────────────────────────────────
  // The cross-tenant ADMIN surface (close-test-coverage-gaps 4.1):
  // /api/v1/admin/tenants/{uuid}/feature-flags/ (admin_urls.py
  // admin-tenant-feature-flags) + /api/v1/admin/feature-flag-approvals/
  // {uuid}/approve/ (admin-feature-flag-approval-approve). The old paths
  // addressed the SELF-SERVICE family (/tenants/{id}/feature-flags/) —
  // only me/feature-flags/ exists there, so every live call 404'd.
  async getTenantFeatureFlags(tenantId: string): Promise<AdminFeatureFlagListResponse> {
    const response = await apiClient
      .getClient()
      .get<AdminFeatureFlagListResponse>(`/admin/tenants/${tenantId}/feature-flags/`);
    return response.data;
  },

  async updateTenantFeatureFlags(
    tenantId: string,
    flags: Record<string, boolean>,
    reason?: string
  ) {
    // PUT is the admin view's method (no PATCH on the admin surface).
    const response = await apiClient.getClient().put<{
      flags: AdminFeatureFlagRow[];
    }>(`/admin/tenants/${tenantId}/feature-flags/`, { flags, reason });
    return response.data;
  },

  async approveFeatureFlagFlip(approvalId: string) {
    const response = await apiClient
      .getClient()
      .post<{ flag: AdminFeatureFlagRow }>(`/admin/feature-flag-approvals/${approvalId}/approve/`);
    return response.data;
  },

  // ── Dashboard ───────────────────────────────────────────────
  async getDashboardSummary() {
    const response = await apiClient.getClient().get<AdminDashboardResponse>('/admin/dashboard/');
    return response.data;
  },

  async refreshDashboardSummary() {
    const response = await apiClient
      .getClient()
      .post<AdminDashboardResponse>('/admin/dashboard/refresh/');
    return response.data;
  },

  // ── Impersonation ───────────────────────────────────────────
  // W5.1 (R2-F1) — the wire contract matches the backend exactly:
  // POST /admin/impersonate/ with {user_id, reason (required, ≥10
  // chars), max_minutes?} (the pre-fix called a nonexistent
  // ``/start/`` URL without the reason — every start 404'd), and
  // POST /admin/impersonate/exit/ with {session_id} (the pre-fix
  // sent no body — the serializer 400'd every exit).
  async startImpersonation(userId: string, reason: string, maxMinutes?: number) {
    const payload: Record<string, unknown> = { user_id: userId, reason };
    if (maxMinutes != null) payload.max_minutes = maxMinutes;
    const response = await apiClient
      .getClient()
      .post<AdminImpersonateSession>('/admin/impersonate/', payload);
    return response.data;
  },

  async exitImpersonation(sessionId: string) {
    const response = await apiClient
      .getClient()
      .post<{ success: boolean }>('/admin/impersonate/exit/', {
        session_id: sessionId,
      });
    return response.data;
  },
};

// ── Admin type exports ──────────────────────────────────────

export interface AdminFeatureFlagRow {
  id: string;
  name: string;
  description?: string;
  enabled: boolean;
  current_value?: boolean;
  tenant_id: string;
  sensitive?: boolean;
  stage?: string;
  updated_at?: string;
}

export interface AdminFeatureFlagListResponse {
  flags: AdminFeatureFlagRow[];
  pending_approvals: Array<{
    id: string;
    flag: AdminFeatureFlagRow;
    requested_by: string;
    requested_at: string;
    requested_value?: string;
    status: string;
  }>;
}

export interface AdminImpersonateSession {
  session: {
    id: string;
    impersonator_user_id: string;
    impersonated_user_id: string;
    impersonator_tenant_id: string | null;
    impersonated_tenant_id: string;
    started_at: string;
    expires_at: string;
    max_minutes: number;
    status: string;
  };
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AdminDashboardResponse {
  tenants: AdminDashboardTenantsWidget;
  audit: AdminDashboardAuditWidget;
  billing: AdminDashboardBillingWidget;
  compliance: AdminDashboardComplianceWidget;
  governance: AdminDashboardGovernanceWidget;
  webhooks: AdminDashboardWebhooksWidget;
  generated_at?: string;
  cache_hit?: boolean;
}

export interface AdminDashboardAuditWidget {
  total_events: number;
  events_24h: number;
  events_last_24h?: number;
  integrity_mismatch_count?: number;
  integrity_verified_at?: string | null;
  status: 'ok' | 'warning' | 'error';
  error?: AdminDashboardWidgetError;
}

export interface AdminDashboardBillingWidget {
  active_subscriptions: number;
  monthly_revenue?: number;
  active: number;
  trial: number;
  past_due: number;
  unpaid: number;
  canceled: number;
  incomplete: number;
  pending_invoices?: number;
  overdue_invoices?: number;
  status: 'ok' | 'warning' | 'error';
  error?: AdminDashboardWidgetError;
}

export interface AdminDashboardComplianceWidget {
  open_findings: number;
  upcoming_audits: number;
  pending?: number;
  running?: number;
  succeeded_last_24h?: number;
  failed_last_24h?: number;
  status: 'ok' | 'warning' | 'error';
  error?: AdminDashboardWidgetError;
}

export interface AdminDashboardGovernanceWidget {
  pending_approvals: number;
  pending_dsars: number;
  open_access_requests: number;
  approved_access_requests: number;
  rejected_access_requests: number;
  status: 'ok' | 'warning' | 'error';
  error?: AdminDashboardWidgetError;
}

export interface AdminDashboardTenantsWidget {
  total: number;
  active: number;
  suspended: number;
  deleted?: number;
  legal_hold?: number;
  scheduled_for_deletion?: number;
  status: 'ok' | 'warning' | 'error';
  error?: AdminDashboardWidgetError;
}

export interface AdminDashboardWebhooksWidget {
  total: number;
  active?: number;
  paused?: number;
  failed_24h: number;
  dlq_size: number;
  delivery_health_last_24h: {
    success: number;
    failed: number;
    dead_letter: number;
    rate_limited: number;
  };
  status: 'ok' | 'warning' | 'error';
  error?: AdminDashboardWidgetError;
}

export interface AdminDashboardWidgetError {
  message: string;
  code?: string;
}

export function isWidgetError(
  widget: { error?: AdminDashboardWidgetError } | AdminDashboardWidgetError
): boolean {
  const obj = widget as Record<string, unknown>;
  // THE backend contract (admin_dashboard_summary.py): a failed widget is
  // replaced by the sentinel payload ``{"widget_error": true}`` — the SPA
  // must recognise it or the failed widget renders its normal layout
  // (Phase 235.5 Gap 2 drift: this check previously only knew the
  // ``error``/message shapes).
  if (obj['widget_error'] === true) {
    return true;
  }
  // Direct error object from backend: has 'message', no 'status' (widget envelopes always have status)
  if (!('status' in obj) && 'message' in obj) {
    return true;
  }
  // Widget envelope with embedded error
  if ('error' in obj) {
    return obj.error !== undefined;
  }
  return false;
}
