/**
 * DQ React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dqService } from '../services/dqService';
import type { DQRunCreateRequest, DQRunListFilters } from '../../../shared/types/dq';

export function useDQRuns(filters: DQRunListFilters = {}) {
  return useQuery({
    queryKey: ['dq', 'runs', 'list', filters],
    queryFn: () => dqService.list(filters),
    refetchInterval: (query) => {
      // Auto-refetch if there are running DQ runs
      const data = query.state.data;
      if (data?.results) {
        const hasRunningRuns = data.results.some(
          (run) => run.status === 'PENDING' || run.status === 'RUNNING'
        );
        return hasRunningRuns ? 2000 : false; // Poll every 2 seconds if running
      }
      return false;
    },
  });
}

export function useDQRun(id: string | null) {
  return useQuery({
    queryKey: ['dq', 'runs', 'detail', id],
    queryFn: () => dqService.getById(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      // Auto-refetch if DQ run is running
      const run = query.state.data;
      if (run && (run.status === 'PENDING' || run.status === 'RUNNING')) {
        return 2000; // Poll every 2 seconds
      }
      return false;
    },
  });
}

export function useDQRunResults(id: string | null) {
  return useQuery({
    queryKey: ['dq', 'runs', 'results', id],
    queryFn: () => dqService.getResults(id!),
    enabled: !!id,
  });
}

export function useCreateDQRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DQRunCreateRequest) => dqService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dq', 'runs'] });
    },
  });
}
