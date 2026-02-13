/**
 * Admin React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
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
