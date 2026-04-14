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
import type {
  ODPSProductCreateRequest,
  ODPSWorkflowStatus,
  ODPSLinkRequest,
  ODPSLinks,
  ODPSExportParams,
} from '../../../shared/types/odps';

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

/**
 * Validate a contract draft without persisting (Phase 219.5).
 * Silent mutation — no toast on success; errors surface in the
 * ValidationResultPanel UI, not as global notifications.
 */
export function useValidateDraft() {
  return useMutationWithNotification({
    mutationFn: (data: { original_raw: string; original_format: string }) =>
      contractService.validateDraft(data),
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

// ---------------------------------------------------------------------------
// ODPS-specific hooks (merged from useODPS.ts)
// ---------------------------------------------------------------------------

/**
 * Poll workflow status until completion or failure.
 * Renamed from useODPSWorkflowStatus → useContractWorkflowStatus for reuse.
 */
export function useContractWorkflowStatus(
  workflowInstanceId: string | null,
  options: {
    enabled?: boolean;
    refetchInterval?: number | false;
  } = {}
) {
  return useQuery<ODPSWorkflowStatus>({
    queryKey: ['contracts', 'workflow', workflowInstanceId],
    queryFn: () => contractService.getWorkflowStatus(workflowInstanceId!),
    enabled: !!workflowInstanceId && (options.enabled !== false),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'COMPLETED' || data?.status === 'FAILED') {
        return false;
      }
      return options.refetchInterval ?? 2000;
    },
  });
}

/** @deprecated Use useContractWorkflowStatus instead */
export const useODPSWorkflowStatus = useContractWorkflowStatus;

/**
 * Create ODPS product (Product-First workflow)
 */
export function useCreateODPSProduct() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: ODPSProductCreateRequest) => contractService.createODPSProduct(data),
    successMessage: 'ODPS product created',
    errorMessage: 'Failed to create ODPS product',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

/**
 * Link ODPS to ODCS contract
 */
export function useLinkODPS() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ odcsContractId, data }: { odcsContractId: string; data: ODPSLinkRequest }) =>
      contractService.linkODPS(odcsContractId, data),
    successMessage: 'ODPS linked',
    errorMessage: 'Failed to link ODPS',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', variables.odcsContractId] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'links', variables.odcsContractId] });
    },
  });
}

/**
 * Unlink ODPS from ODCS contract
 */
export function useUnlinkODPS() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (odcsContractId: string) => contractService.unlinkODPS(odcsContractId),
    successMessage: 'ODPS unlinked',
    errorMessage: 'Failed to unlink ODPS',
    onSuccess: (_, odcsContractId) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', odcsContractId] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'links', odcsContractId] });
    },
  });
}

/**
 * Get contract links (ODPS ↔ ODCS bidirectional)
 */
export function useContractLinks(contractId: string | null) {
  return useQuery<ODPSLinks>({
    queryKey: ['contracts', 'links', contractId],
    queryFn: () => contractService.getLinks(contractId!),
    enabled: !!contractId,
    select: (data) => data ?? { odps_link: null, odcs_link: null },
  });
}

/** @deprecated Use useContractLinks instead */
export const useODPSLinks = useContractLinks;

/**
 * Export ODPS contract with format options
 */
export function useExportODPS() {
  return useMutationWithNotification({
    mutationFn: ({ contractId, params }: { contractId: string; params?: ODPSExportParams }) =>
      contractService.exportODPS(contractId, params),
    successMessage: 'ODPS exported',
    errorMessage: 'Failed to export ODPS',
  });
}

/**
 * Download ODPS contract with format options
 */
export function useDownloadODPS() {
  return useMutationWithNotification({
    mutationFn: ({ contractId, params }: { contractId: string; params?: ODPSExportParams }) =>
      contractService.downloadODPS(contractId, params),
    successMessage: 'ODPS downloaded',
    errorMessage: 'Failed to download ODPS',
  });
}

// ---------------------------------------------------------------------------
// Lineage
// ---------------------------------------------------------------------------

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
