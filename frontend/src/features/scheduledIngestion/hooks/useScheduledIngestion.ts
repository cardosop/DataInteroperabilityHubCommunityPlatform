/**
 * Scheduled Ingestion React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type {
  ScheduledIngestionListFilters,
  ScheduledIngestionCreateRequest,
  ScheduledIngestionUpdateRequest,
  ScheduledIngestionTriggerRequest,
} from '../../../shared/types/scheduledIngestion';
import { scheduledIngestionService } from '../services/scheduledIngestionService';

export function useScheduledIngestions(filters: ScheduledIngestionListFilters = {}) {
  return useQuery({
    queryKey: ['scheduled-ingestions', 'list', filters],
    queryFn: async () => {
      const data = await scheduledIngestionService.list(filters);
      if (data == null) {
        return { results: [], count: 0, next: null, previous: null };
      }
      return data;
    },
  });
}

export function useScheduledIngestion(id: string | null) {
  return useQuery({
    queryKey: ['scheduled-ingestions', 'detail', id],
    queryFn: () => scheduledIngestionService.getById(id!),
    enabled: !!id,
  });
}

export function useScheduledIngestionRuns(id: string | null) {
  return useQuery({
    queryKey: ['scheduled-ingestions', 'runs', id],
    queryFn: () => scheduledIngestionService.listRuns(id!),
    enabled: !!id,
  });
}

export function useCreateScheduledIngestion() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: ScheduledIngestionCreateRequest) => scheduledIngestionService.create(data),
    successMessage: 'Scheduled ingestion created',
    errorMessage: 'Failed to create scheduled ingestion',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-ingestions'] });
    },
  });
}

export function useUpdateScheduledIngestion() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: ScheduledIngestionUpdateRequest }) =>
      scheduledIngestionService.update(id, data),
    successMessage: 'Scheduled ingestion updated',
    errorMessage: 'Failed to update scheduled ingestion',
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-ingestions'] });
      queryClient.invalidateQueries({
        queryKey: ['scheduled-ingestions', 'detail', data.id],
      });
    },
  });
}

export function useDeleteScheduledIngestion() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => scheduledIngestionService.delete(id),
    successMessage: 'Scheduled ingestion deleted',
    errorMessage: 'Failed to delete scheduled ingestion',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-ingestions'] });
    },
  });
}

export function useTriggerScheduledIngestion() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data?: ScheduledIngestionTriggerRequest }) =>
      scheduledIngestionService.trigger(id, data),
    successMessage: 'Scheduled ingestion triggered',
    errorMessage: 'Failed to trigger scheduled ingestion',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-ingestions'] });
      queryClient.invalidateQueries({
        queryKey: ['scheduled-ingestions', 'detail', variables.id],
      });
      queryClient.invalidateQueries({
        queryKey: ['scheduled-ingestions', 'runs', variables.id],
      });
    },
  });
}
