/**
 * Contracts React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { emptyPaginatedResponse } from '../../../shared/types/api';
import { contractService } from '../services/contractService';
import type {
  Contract,
  ContractCreateRequest,
  ContractUpdateRequest,
  ContractListFilters,
  ContractConvertRequest,
} from '../../../shared/types/contracts';
import type { ContractLineageVisualizationParams } from '../../../shared/types/lineage';

export function useContracts(
  filters: ContractListFilters = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['contracts', 'list', filters],
    queryFn: async () => {
      const data = await contractService.list(filters);
      if (data === undefined) {
        return emptyPaginatedResponse<Contract>();
      }
      return data;
    },
    enabled: options?.enabled !== false,
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

  return useMutationWithNotification({
    mutationFn: (data: ContractCreateRequest) => contractService.create(data),
    successMessage: 'Contract created',
    errorMessage: 'Failed to create contract',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

export function useUpdateContract() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: ContractUpdateRequest }) =>
      contractService.update(id, data),
    successMessage: 'Contract updated',
    errorMessage: 'Failed to update contract',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', variables.id] });
    },
  });
}

export function useDeleteContract() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => contractService.delete(id),
    successMessage: 'Contract deleted',
    errorMessage: 'Failed to delete contract',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

export function useValidateContract() {
  return useMutationWithNotification({
    mutationFn: (id: string) => contractService.validate(id),
    successMessage: 'Contract validated',
    errorMessage: 'Validation failed',
  });
}

export function useLintContract() {
  return useMutationWithNotification({
    mutationFn: (id: string) => contractService.lint(id),
    successMessage: 'Contract linted',
    errorMessage: 'Linting failed',
  });
}

export function useConvertContract() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: ContractConvertRequest }) =>
      contractService.convert(id, data),
    successMessage: 'Contract converted',
    errorMessage: 'Failed to convert contract',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', variables.id] });
    },
  });
}

export function useExportContract() {
  return useMutationWithNotification({
    mutationFn: ({ id, format }: { id: string; format?: string }) =>
      contractService.export(id, format),
    successMessage: 'Contract exported',
    errorMessage: 'Failed to export contract',
  });
}

export function useDownloadContract() {
  return useMutationWithNotification({
    mutationFn: ({ id, format }: { id: string; format?: string }) =>
      contractService.download(id, format),
    successMessage: 'Contract downloaded',
    errorMessage: 'Failed to download contract',
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
