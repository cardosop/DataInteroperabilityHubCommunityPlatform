/**
 * Datasets React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { emptyPaginatedResponse } from '../../../shared/types/api';
import { datasetService } from '../services/datasetService';
import type {
  Dataset,
  DatasetCreateRequest,
  DatasetUpdateRequest,
  DatasetListFilters,
} from '../../../shared/types/datasets';

export function useDatasets(
  filters: DatasetListFilters = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['datasets', 'list', filters],
    queryFn: async () => {
      const data = await datasetService.list(filters);
      if (data === undefined) {
        return emptyPaginatedResponse<Dataset>();
      }
      return data;
    },
    enabled: options?.enabled !== false,
  });
}

export function useDataset(id: string | null) {
  return useQuery({
    queryKey: ['datasets', 'detail', id],
    queryFn: () => datasetService.getById(id!),
    enabled: !!id,
  });
}

export function useDatasetVersions(id: string | null) {
  return useQuery({
    queryKey: ['datasets', 'versions', id],
    queryFn: () => datasetService.getVersions(id!),
    enabled: !!id,
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: DatasetCreateRequest) => datasetService.create(data),
    successMessage: 'Dataset created',
    errorMessage: 'Failed to create dataset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: DatasetUpdateRequest }) =>
      datasetService.update(id, data),
    successMessage: 'Dataset updated',
    errorMessage: 'Failed to update dataset',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      queryClient.invalidateQueries({ queryKey: ['datasets', 'detail', variables.id] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => datasetService.delete(id),
    successMessage: 'Dataset deleted',
    errorMessage: 'Failed to delete dataset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}
