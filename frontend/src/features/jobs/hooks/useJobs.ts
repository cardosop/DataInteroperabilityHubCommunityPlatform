/**
 * Jobs React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { emptyPaginatedResponse } from '../../../shared/types/api';
import { jobService } from '../services/jobService';
import type { Job, JobCreateRequest, JobListFilters } from '../../../shared/types/jobs';

export function useJobs(filters: JobListFilters = {}) {
  return useQuery({
    queryKey: ['jobs', 'list', filters],
    queryFn: async () => {
      const data = await jobService.list(filters);
      if (data === undefined) {
        return emptyPaginatedResponse<Job>();
      }
      return data;
    },
    refetchInterval: (query) => {
      // Auto-refetch if there are running jobs
      const data = query.state.data;
      if (data?.results) {
        const hasRunningJobs = data.results.some(
          (job) => job.status === 'PENDING' || job.status === 'RUNNING'
        );
        return hasRunningJobs ? 2000 : false; // Poll every 2 seconds if running
      }
      return false;
    },
  });
}

export function useJob(id: string | null) {
  return useQuery({
    queryKey: ['jobs', 'detail', id],
    queryFn: () => jobService.getById(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      // Auto-refetch if job is running
      const job = query.state.data;
      if (job && (job.status === 'PENDING' || job.status === 'RUNNING')) {
        return 2000; // Poll every 2 seconds
      }
      return false;
    },
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: JobCreateRequest) => jobService.create(data),
    successMessage: 'Job created',
    errorMessage: 'Failed to create job',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => jobService.cancel(id),
    successMessage: 'Job cancelled',
    errorMessage: 'Failed to cancel job',
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['jobs', 'detail', id] });
    },
  });
}
