/**
 * Assets React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  AssetCreateRequest,
  AssetListFilters,
  AssetUpdateRequest,
  AttachContractRequest,
  AttachDatasetRequest,
} from '../../../shared/types/assets';
import { assetService } from '../services/assetService';

export function useAssets(filters: AssetListFilters = {}) {
  return useQuery({
    queryKey: ['assets', 'list', filters],
    queryFn: () => assetService.list(filters),
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
      // Update the asset in cache with the response (which includes dataset_id)
      queryClient.setQueryData(['assets', 'detail', variables.id], updatedAsset);
      // Also invalidate to ensure fresh data
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['assets'] });
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

export function useAssetRecommendations(
  filters: {
    asset_id?: string;
    user_id?: string;
    limit?: number;
  } = {}
) {
  return useQuery({
    queryKey: ['assets', 'recommendations', filters],
    queryFn: () => assetService.getRecommendations(filters),
  });
}
