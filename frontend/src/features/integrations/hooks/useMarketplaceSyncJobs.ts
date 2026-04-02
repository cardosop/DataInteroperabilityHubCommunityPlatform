/**
 * Marketplace Sync Jobs React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { marketplaceSyncJobService } from '../services/marketplaceSyncJobService';
import type {
  MarketplaceSyncJob,
  MarketplaceSyncJobCreate,
  MarketplaceSyncJobCancel,
  MarketplaceSyncJobListFilters,
} from '../../../shared/types/integrations';

export function useMarketplaceSyncJobs(filters: MarketplaceSyncJobListFilters = {}) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'sync', 'list', filters],
    queryFn: () => marketplaceSyncJobService.list(filters),
    // Auto-refetch for running jobs
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.results) {
        const hasRunning = data.results.some(
          (job: MarketplaceSyncJob) => job.status === 'RUNNING' || job.status === 'PENDING'
        );
        return hasRunning ? 2000 : false;
      }
      return false;
    },
  });
}

export function useMarketplaceSyncJob(id: string | null) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'sync', 'detail', id],
    queryFn: () => marketplaceSyncJobService.getById(id!),
    enabled: !!id,
    // Auto-refetch for running jobs
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'RUNNING' || data.status === 'PENDING')) {
        return 2000;
      }
      return false;
    },
  });
}

export function useCreateMarketplaceSyncJob() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: MarketplaceSyncJobCreate) => marketplaceSyncJobService.create(data),
    successMessage: 'Sync job created',
    errorMessage: 'Failed to create sync job',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'sync'] });
    },
  });
}

export function useCancelMarketplaceSyncJob() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data?: MarketplaceSyncJobCancel }) =>
      marketplaceSyncJobService.cancel(id, data),
    successMessage: 'Sync job cancelled',
    errorMessage: 'Failed to cancel sync job',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'sync'] });
      queryClient.invalidateQueries({ queryKey: ['integrations', 'marketplace', 'sync', 'detail', variables.id] });
    },
  });
}
