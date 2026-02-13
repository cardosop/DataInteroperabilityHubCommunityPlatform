/**
 * Marketplace Connections React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { marketplaceConnectionService } from '../services/marketplaceConnectionService';
import type {
  MarketplaceConnectionCreate,
  MarketplaceConnectionUpdate,
  MarketplaceConnectionListFilters,
} from '../../../shared/types/integrations';

export function useMarketplaceConnections(filters: MarketplaceConnectionListFilters = {}) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'connections', 'list', filters],
    queryFn: () => marketplaceConnectionService.list(filters),
  });
}

export function useMarketplaceConnection(id: string | null) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'connections', 'detail', id],
    queryFn: () => marketplaceConnectionService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateMarketplaceConnection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: MarketplaceConnectionCreate) => marketplaceConnectionService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'connections'] });
    },
  });
}

export function useUpdateMarketplaceConnection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MarketplaceConnectionUpdate }) =>
      marketplaceConnectionService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'connections'] });
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'connections', 'detail', variables.id] });
    },
  });
}

export function usePartialUpdateMarketplaceConnection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<MarketplaceConnectionUpdate> }) =>
      marketplaceConnectionService.partialUpdate(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'connections'] });
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'connections', 'detail', variables.id] });
    },
  });
}

export function useDeleteMarketplaceConnection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => marketplaceConnectionService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'connections'] });
    },
  });
}

export function useTestMarketplaceConnection() {
  return useMutation({
    mutationFn: (id: string) => marketplaceConnectionService.test(id),
  });
}
