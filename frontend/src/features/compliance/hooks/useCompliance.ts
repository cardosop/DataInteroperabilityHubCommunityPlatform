/**
 * Compliance React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { complianceService } from '../services/complianceService';
import type {
  ComplianceRunCreateRequest,
  ComplianceRunListFilters,
} from '../../../shared/types/compliance';

export function useComplianceRuns(filters: ComplianceRunListFilters = {}) {
  return useQuery({
    queryKey: ['compliance', 'runs', 'list', filters],
    queryFn: () => complianceService.list(filters),
    refetchInterval: (query) => {
      // Auto-refetch if there are running compliance runs
      const data = query.state.data;
      if (data?.results) {
        const hasRunningRuns = data.results.some(
          (run) => run.status === 'PENDING' || run.status === 'QUEUED' || run.status === 'RUNNING'
        );
        return hasRunningRuns ? 2000 : false; // Poll every 2 seconds if running
      }
      return false;
    },
  });
}

export function useComplianceRun(id: string | null) {
  return useQuery({
    queryKey: ['compliance', 'runs', 'detail', id],
    queryFn: () => complianceService.getById(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      // Auto-refetch if compliance run is running
      const run = query.state.data;
      if (run && (run.status === 'PENDING' || run.status === 'QUEUED' || run.status === 'RUNNING')) {
        return 2000; // Poll every 2 seconds
      }
      return false;
    },
  });
}

export function useComplianceRunResults(id: string | null) {
  return useQuery({
    queryKey: ['compliance', 'runs', 'results', id],
    queryFn: () => complianceService.getResults(id!),
    enabled: !!id,
  });
}

export function useCreateComplianceRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ComplianceRunCreateRequest) => complianceService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compliance', 'runs'] });
    },
  });
}

export function useCancelComplianceRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => complianceService.cancel(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['compliance', 'runs'] });
      queryClient.invalidateQueries({ queryKey: ['compliance', 'runs', 'detail', id] });
    },
  });
}

export function useDeleteComplianceRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => complianceService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compliance', 'runs'] });
    },
  });
}
