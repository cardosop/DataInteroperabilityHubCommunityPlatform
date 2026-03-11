/**
 * Scheduled Ingestion React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  return useMutation({
    mutationFn: (data: ScheduledIngestionCreateRequest) => scheduledIngestionService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-ingestions'] });
    },
  });
}

export function useUpdateScheduledIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ScheduledIngestionUpdateRequest }) =>
      scheduledIngestionService.update(id, data),
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
  return useMutation({
    mutationFn: (id: string) => scheduledIngestionService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-ingestions'] });
    },
  });
}

export function useTriggerScheduledIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: ScheduledIngestionTriggerRequest }) =>
      scheduledIngestionService.trigger(id, data),
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
