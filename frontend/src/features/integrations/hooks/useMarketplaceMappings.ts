/**
 * Marketplace Mappings React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { marketplaceMappingService } from '../services/marketplaceMappingService';
import type { MarketplaceMappingListFilters } from '../../../shared/types/integrations';

export function useMarketplaceMappings(filters: MarketplaceMappingListFilters = {}) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'mappings', 'list', filters],
    queryFn: () => marketplaceMappingService.list(filters),
  });
}

export function useMarketplaceMapping(id: string | null) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'mappings', 'detail', id],
    queryFn: () => marketplaceMappingService.getById(id!),
    enabled: !!id,
  });
}

export function useDeleteMarketplaceMapping() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => marketplaceMappingService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'mappings'] });
    },
  });
}
