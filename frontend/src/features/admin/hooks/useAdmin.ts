/**
 * Admin React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type { TenantListFilters } from '../../../shared/types/tenants';
import type { UserListFilters } from '../../../shared/types/users';
import { adminService } from '../services/adminService';

export function useTenants(filters: TenantListFilters = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['admin', 'tenants', 'list', filters],
    queryFn: () => adminService.listTenants(filters),
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
    queryFn: () => adminService.listUsers(filters),
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
    queryFn: () => adminService.getPlatformTenantUsage(),
    enabled: options?.enabled !== false,
  });
}
