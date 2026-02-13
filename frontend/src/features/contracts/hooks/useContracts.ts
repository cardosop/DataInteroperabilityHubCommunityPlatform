/**
 * Contracts React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { contractService } from '../services/contractService';
import type {
  ContractCreateRequest,
  ContractUpdateRequest,
  ContractListFilters,
  ContractConvertRequest,
} from '../../../shared/types/contracts';
import type { ContractLineageVisualizationParams } from '../../../shared/types/lineage';

export function useContracts(filters: ContractListFilters = {}) {
  return useQuery({
    queryKey: ['contracts', 'list', filters],
    queryFn: () => contractService.list(filters),
  });
}

export function useContract(id: string | null) {
  return useQuery({
    queryKey: ['contracts', 'detail', id],
    queryFn: () => contractService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ContractCreateRequest) => contractService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

export function useUpdateContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ContractUpdateRequest }) =>
      contractService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', variables.id] });
    },
  });
}

export function useDeleteContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => contractService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

export function useValidateContract() {
  return useMutation({
    mutationFn: (id: string) => contractService.validate(id),
  });
}

export function useLintContract() {
  return useMutation({
    mutationFn: (id: string) => contractService.lint(id),
  });
}

export function useConvertContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ContractConvertRequest }) =>
      contractService.convert(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', variables.id] });
    },
  });
}

export function useExportContract() {
  return useMutation({
    mutationFn: ({ id, format }: { id: string; format?: string }) =>
      contractService.export(id, format),
  });
}

export function useDownloadContract() {
  return useMutation({
    mutationFn: ({ id, format }: { id: string; format?: string }) =>
      contractService.download(id, format),
  });
}

/**
 * Hook to fetch contract lineage visualization (real API; no stub data).
 * GET /api/v1/contracts/{id}/lineage/visualization/?format=json&max_depth=...
 */
export function useContractLineageVisualization(
  contractId: string | null,
  params: ContractLineageVisualizationParams = {}
) {
  return useQuery({
    queryKey: ['contracts', 'lineage', contractId, params],
    queryFn: () => contractService.getLineageVisualization(contractId!, params),
    enabled: !!contractId,
  });
}
