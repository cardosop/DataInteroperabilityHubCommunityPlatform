/**
 * Admin React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { normalizePaginated } from '../../../shared/utils/paginated';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type { TenantListFilters } from '../../../shared/types/tenants';
import type { UserListFilters } from '../../../shared/types/users';
import { adminService } from '../services/adminService';

export function useTenants(filters: TenantListFilters = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['admin', 'tenants', 'list', filters],
    queryFn: async () => normalizePaginated(await adminService.listTenants(filters)),
    enabled: options?.enabled !== false,
  });
}

export function useTenant(id: string | null) {
  return useQuery({
    queryKey: ['admin', 'tenants', 'detail', id],
    queryFn: () => adminService.getTenant(id!),
    enabled: !!id,
  });
}

export function useTenantConfig(tenantId: string | null) {
  return useQuery({
    queryKey: ['admin', 'tenants', 'config', tenantId],
    queryFn: () => adminService.getTenantConfig(tenantId!),
    enabled: !!tenantId,
  });
}

export function useUsers(filters: UserListFilters = {}) {
  return useQuery({
    queryKey: ['admin', 'users', 'list', filters],
    queryFn: async () => normalizePaginated(await adminService.listUsers(filters)),
  });
}

export function useUser(id: string | null) {
  return useQuery({
    queryKey: ['admin', 'users', 'detail', id],
    queryFn: () => adminService.getUser(id!),
    enabled: !!id,
  });
}

export function useRoles() {
  return useQuery({
    queryKey: ['admin', 'roles', 'list'],
    queryFn: () => adminService.listRoles(),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { display_name?: string; status?: string; role_ids?: string[] };
    }) => adminService.updateUser(id, data),
    successMessage: 'User updated',
    errorMessage: 'Failed to update user',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'detail', variables.id] });
    },
  });
}

export function useCreateTenant() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: { name: string; slug: string; region?: string }) =>
      adminService.createTenant(data),
    successMessage: 'Organization created',
    errorMessage: 'Failed to create organization',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tenants', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'platform', 'usage'] });
    },
  });
}

export function useSuspendTenant() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      adminService.suspendTenant(id, reason),
    successMessage: 'Tenant suspended',
    errorMessage: 'Failed to suspend tenant',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tenants', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'tenants', 'detail', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'platform', 'usage'] });
    },
  });
}

export function useResumeTenant() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id }: { id: string }) => adminService.resumeTenant(id),
    successMessage: 'Tenant resumed',
    errorMessage: 'Failed to resume tenant',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tenants', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'tenants', 'detail', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'platform', 'usage'] });
    },
  });
}

export function usePlatformTenantUsage(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['admin', 'platform', 'usage'],
    queryFn: async () => normalizePaginated(await adminService.getPlatformTenantUsage()),
    enabled: options?.enabled !== false,
  });
}

// ── Feature flags ────────────────────────────────────────────

export function useAdminTenantFeatureFlags(tenantId: string | null) {
  return useQuery({
    queryKey: ['admin', 'tenants', 'feature-flags', tenantId],
    queryFn: () => adminService.getTenantFeatureFlags(tenantId!),
    enabled: !!tenantId,
  });
}

export function useUpdateAdminTenantFeatureFlags() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({
      tenantId,
      flags,
      reason,
    }: {
      tenantId: string;
      flags: Record<string, boolean>;
      reason?: string;
    }) => adminService.updateTenantFeatureFlags(tenantId, flags, reason),
    successMessage: 'Feature flags updated',
    errorMessage: 'Failed to update feature flags',
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['admin', 'tenants', 'feature-flags', variables.tenantId],
      });
    },
  });
}

export function useApproveFeatureFlagFlip() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ flagId }: { tenantId: string; flagId: string }) =>
      adminService.approveFeatureFlagFlip(flagId),
    successMessage: 'Feature flag change approved',
    errorMessage: 'Failed to approve feature flag change',
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['admin', 'tenants', 'feature-flags', variables.tenantId],
      });
    },
  });
}

// ── Dashboard ─────────────────────────────────────────────────

export function useAdminDashboardSummary(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['admin', 'dashboard', 'summary'],
    queryFn: () => adminService.getDashboardSummary(),
    enabled: options?.enabled !== false,
  });
}

export function useRefreshAdminDashboardSummary() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: () => adminService.refreshDashboardSummary(),
    successMessage: 'Dashboard refreshed',
    errorMessage: 'Failed to refresh dashboard',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    },
  });
}

// ── Impersonation ─────────────────────────────────────────────

export function useAdminImpersonateStart() {
  return useMutationWithNotification({
    mutationFn: ({
      userId,
      reason,
      maxMinutes,
    }: {
      userId: string;
      reason: string;
      maxMinutes?: number;
    }) => adminService.startImpersonation(userId, reason, maxMinutes),
    successMessage: 'Impersonation started',
    errorMessage: 'Failed to start impersonation',
  });
}

export function useAdminImpersonateExit() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ sessionId }: { sessionId: string }) =>
      adminService.exitImpersonation(sessionId),
    successMessage: 'Impersonation ended',
    errorMessage: 'Failed to exit impersonation',
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}
