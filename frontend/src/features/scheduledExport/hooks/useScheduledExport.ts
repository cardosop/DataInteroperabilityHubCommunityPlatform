/**
 * Scheduled Export React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  ScheduledExportCreateRequest,
  ScheduledExportListFilters,
  ScheduledExportTriggerRequest,
  ScheduledExportUpdateRequest,
} from '../../../shared/types/scheduledExport';
import { scheduledExportService } from '../services/scheduledExportService';

export function useScheduledExports(filters: ScheduledExportListFilters = {}) {
  return useQuery({
    queryKey: ['scheduled-exports', 'list', filters],
    queryFn: () => scheduledExportService.list(filters),
  });
}

export function useScheduledExport(id: string | null) {
  return useQuery({
    queryKey: ['scheduled-exports', 'detail', id],
    queryFn: () => scheduledExportService.getById(id!),
    enabled: !!id,
  });
}

export function useScheduledExportRuns(id: string | null) {
  return useQuery({
    queryKey: ['scheduled-exports', 'runs', id],
    queryFn: () => scheduledExportService.listRuns(id!),
    enabled: !!id,
  });
}

export function useCreateScheduledExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ScheduledExportCreateRequest) => scheduledExportService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-exports'] });
    },
  });
}

export function useUpdateScheduledExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ScheduledExportUpdateRequest }) =>
      scheduledExportService.update(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-exports'] });
      queryClient.invalidateQueries({
        queryKey: ['scheduled-exports', 'detail', data.id],
      });
    },
  });
}

export function useDeleteScheduledExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scheduledExportService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-exports'] });
    },
  });
}

export function useTriggerScheduledExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: ScheduledExportTriggerRequest }) =>
      scheduledExportService.trigger(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-exports'] });
      queryClient.invalidateQueries({
        queryKey: ['scheduled-exports', 'detail', variables.id],
      });
      queryClient.invalidateQueries({
        queryKey: ['scheduled-exports', 'runs', variables.id],
      });
    },
  });
}
