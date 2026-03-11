/**
 * Assets React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { emptyPaginatedResponse } from '../../../shared/types/api';
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

  return useMutation({
    mutationFn: (data: AssetCreateRequest) => assetService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useUpdateAsset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AssetUpdateRequest }) =>
      assetService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
    },
  });
}

export function useDeleteAsset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => assetService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

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

export function useAttachContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AttachContractRequest }) =>
      assetService.attachContract(id, data),
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

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AttachDatasetRequest }) =>
      assetService.attachDataset(id, data),
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
  return useMutation({
    mutationFn: ({ id, breakdown }: { id: string; breakdown?: boolean }) =>
      assetService.getHealthScore(id, { recalculate: true, breakdown: breakdown ?? true }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets', 'health-score', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
    },
  });
}

export function useDataFirstAsset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      file_id: string;
      key: string;
      name: string;
      description?: string;
      domain?: string;
    }) => assetService.createDataFirst(data),
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
