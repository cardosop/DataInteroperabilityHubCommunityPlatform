/**
 * Assets React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { emptyPaginatedResponse, isApiError } from '../../../shared/types/api';
import type {
  Asset,
  AssetCreateRequest,
  AssetListFilters,
  AssetUpdateRequest,
  AttachContractRequest,
  AttachDatasetRequest,
} from '../../../shared/types/assets';
import { assetService } from '../services/assetService';

export function useAssets(
  filters: AssetListFilters = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['assets', 'list', filters],
    queryFn: async () => {
      const data = await assetService.list(filters);
      if (data === undefined) {
        return emptyPaginatedResponse<Asset>();
      }
      return data;
    },
    enabled: options?.enabled !== false,
  });
}

export function useAsset(id: string | null) {
  return useQuery({
    queryKey: ['assets', 'detail', id],
    queryFn: () => assetService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateAsset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: AssetCreateRequest) => assetService.create(data),
    successMessage: 'Asset created',
    errorMessage: 'Failed to create asset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useUpdateAsset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: async ({ id, data }: { id: string; data: AssetUpdateRequest }) => {
      const detailKey = ['assets', 'detail', id] as const;
      const cachedAsset = queryClient.getQueryData<Asset>(detailKey);
      let ifMatch =
        typeof cachedAsset?.version === 'number' ? String(cachedAsset.version) : undefined;
      if (!ifMatch) {
        const freshAsset = await queryClient.fetchQuery({
          queryKey: detailKey,
          queryFn: () => assetService.getById(id),
        });
        ifMatch = String(freshAsset.version);
      }

      try {
        return await assetService.update(id, data, { ifMatch });
      } catch (error) {
        const isPreconditionFailed =
          isApiError(error) &&
          error.error.http_status === 412 &&
          error.error.code === 'PRECONDITION_FAILED';
        if (!isPreconditionFailed) {
          throw error;
        }

        // Refresh latest server state, then replay local patch fields once.
        const freshAsset = await queryClient.fetchQuery({
          queryKey: detailKey,
          queryFn: () => assetService.getById(id),
        });
        return assetService.update(id, data, { ifMatch: String(freshAsset.version) });
      }
    },
    successMessage: 'Asset updated',
    errorMessage: (error) => {
      if (
        isApiError(error) &&
        error.error.http_status === 412 &&
        error.error.code === 'PRECONDITION_FAILED'
      ) {
        return 'Asset changed on the server. We refreshed the latest version; review and retry your update.';
      }
      return 'Failed to update asset';
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
    },
  });
}

export function useDeleteAsset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => assetService.delete(id),
    successMessage: 'Asset deleted',
    errorMessage: 'Failed to delete asset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

/**
 * Activate asset mutation — uses raw useMutation (no auto-toast).
 * Callers must handle success/error notifications themselves because activation
 * can fail with ASSET_ACTIVATION_BLOCKED which needs a custom dialog, not a toast.
 */
export function useActivateAsset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      assetService.activate(id, version),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
    },
  });
}

export function useRetireAsset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      assetService.retire(id, version),
    successMessage: 'Asset retired',
    errorMessage: 'Failed to retire asset',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
    },
  });
}

export function useAttachContract() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: AttachContractRequest }) =>
      assetService.attachContract(id, data),
    successMessage: 'Contract attached',
    errorMessage: 'Failed to attach contract',
    onSuccess: (updatedAsset, variables) => {
      // Update the asset in cache with the response (which includes contract_id)
      queryClient.setQueryData(['assets', 'detail', variables.id], updatedAsset);
      // Also invalidate to ensure fresh data
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useAttachDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: AttachDatasetRequest }) =>
      assetService.attachDataset(id, data),
    successMessage: 'Dataset attached',
    errorMessage: 'Failed to attach dataset',
    onSuccess: (updatedAsset, variables) => {
      // Update the asset in cache immediately (reduces refetch dependency)
      queryClient.setQueryData(['assets', 'detail', variables.id], updatedAsset);
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      // Dataset may have asset_id updated; invalidate datasets list
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useAssetHealthScore(
  assetId: string | null,
  options?: { recalculate?: boolean; breakdown?: boolean }
) {
  return useQuery({
    queryKey: ['assets', 'health-score', assetId, options],
    queryFn: () => assetService.getHealthScore(assetId!, options),
    enabled: !!assetId,
  });
}

export function useRecalculateHealthScore() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, breakdown }: { id: string; breakdown?: boolean }) =>
      assetService.getHealthScore(id, { recalculate: true, breakdown: breakdown ?? true }),
    successMessage: 'Health score recalculated',
    errorMessage: 'Failed to recalculate health score',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets', 'health-score', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
    },
  });
}

export function useDataFirstAsset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: {
      file_id: string;
      key: string;
      name: string;
      description?: string;
      domain?: string;
    }) => assetService.createDataFirst(data),
    successMessage: 'Asset created',
    errorMessage: 'Failed to create asset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

export function useAssetRecommendations(
  filters: {
    asset_id?: string;
    user_id?: string;
    limit?: number;
  } = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['assets', 'recommendations', filters],
    queryFn: async () => {
      const data = await assetService.getRecommendations(filters);
      if (data === undefined) {
        return [];
      }
      return data;
    },
    enabled: options?.enabled !== false,
  });
}
