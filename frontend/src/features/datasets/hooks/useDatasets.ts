/**
 * Datasets React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { emptyPaginatedResponse } from '../../../shared/types/api';
import { normalizePaginated } from '../../../shared/utils/paginated';
import { datasetService } from '../services/datasetService';
import type {
  Dataset,
  DatasetCreateRequest,
  DatasetUpdateRequest,
  DatasetListFilters,
} from '../../../shared/types/datasets';

export function useDatasets(filters: DatasetListFilters = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['datasets', 'list', filters],
    queryFn: async () => {
      const data = await datasetService.list(filters);
      return normalizePaginated(data ?? emptyPaginatedResponse<Dataset>());
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
    onSuccess: (_dataset, variables) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      // When the dataset is linked to an asset at creation, the asset's
      // serialized dataset_id changes. Invalidate the asset queries so
      // AssetDetailPage picks up the new dataset_id and renders dataset-
      // gated controls like "Run DQ Check" on first re-fetch.
      if (variables.asset_id) {
        queryClient.invalidateQueries({ queryKey: ['assets'] });
      }
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

/**
 * Phase 260.4.A.1 — retire a dataset (POST /datasets/{id}/retire/).
 * Invalidates the detail (badge/CTA re-render contract) and every list
 * query (the "Show retired" toggle surface).
 */
export function useRetireDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => datasetService.retire(id),
    successMessage: 'Dataset retired',
    errorMessage: 'Failed to retire dataset',
    onSuccess: (_dataset, id) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      queryClient.invalidateQueries({ queryKey: ['datasets', 'detail', id] });
    },
  });
}

/**
 * Fetch sample data rows from a dataset.
 * GET /api/v1/datasets/{id}/sample/?limit=50
 */
export function useRefreshDatasetFromFile() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ datasetId, fileId }: { datasetId: string; fileId: string }) =>
      datasetService.refreshFromFile(datasetId, fileId),
    successMessage: 'Dataset refreshed from file',
    errorMessage: 'Failed to refresh dataset from file',
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['datasets', 'detail', variables.datasetId] });
    },
  });
}

export function useDatasetSample(datasetId: string | null, limit = 50) {
  return useQuery({
    queryKey: ['datasets', 'sample', datasetId, limit],
    queryFn: () => datasetService.getSample(datasetId!, limit),
    enabled: !!datasetId,
  });
}
