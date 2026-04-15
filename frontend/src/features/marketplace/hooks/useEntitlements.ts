/**
 * Entitlements React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { entitlementService } from '../services/entitlementService';
import type {
  EntitlementListFilters,
  CheckAccessRequest,
} from '../../../shared/types/marketplace';

export function useEntitlements(
  filters: EntitlementListFilters = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['marketplace', 'entitlements', 'list', filters],
    queryFn: () => entitlementService.list(filters),
    enabled: options?.enabled !== false,
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
  return useMutationWithNotification({
    mutationFn: (data: CheckAccessRequest) => entitlementService.checkAccess(data),
    successMessage: 'Access checked',
    errorMessage: 'Failed to check access',
  });
}

export function useRevokeEntitlement() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => entitlementService.revoke(id),
    successMessage: 'Entitlement revoked',
    errorMessage: 'Failed to revoke entitlement',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}
