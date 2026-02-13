/**
 * Datasets React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { datasetService } from '../services/datasetService';
import type {
  DatasetCreateRequest,
  DatasetUpdateRequest,
  DatasetListFilters,
} from '../../../shared/types/datasets';

export function useDatasets(filters: DatasetListFilters = {}) {
  return useQuery({
    queryKey: ['datasets', 'list', filters],
    queryFn: () => datasetService.list(filters),
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

  return useMutation({
    mutationFn: (data: DatasetCreateRequest) => datasetService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DatasetUpdateRequest }) =>
      datasetService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      queryClient.invalidateQueries({ queryKey: ['datasets', 'detail', variables.id] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => datasetService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}
