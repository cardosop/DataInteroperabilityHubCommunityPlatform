/**
 * Entitlements React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { entitlementService } from '../services/entitlementService';
import type {
  EntitlementListFilters,
  CheckAccessRequest,
} from '../../../shared/types/marketplace';

export function useEntitlements(filters: EntitlementListFilters = {}) {
  return useQuery({
    queryKey: ['marketplace', 'entitlements', 'list', filters],
    queryFn: () => entitlementService.list(filters),
  });
}

export function useEntitlement(id: string | null) {
  return useQuery({
    queryKey: ['marketplace', 'entitlements', 'detail', id],
    queryFn: () => entitlementService.getById(id!),
    enabled: !!id,
  });
}

export function useCheckAccess() {
  return useMutation({
    mutationFn: (data: CheckAccessRequest) => entitlementService.checkAccess(data),
  });
}

export function useRevokeEntitlement() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => entitlementService.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}
