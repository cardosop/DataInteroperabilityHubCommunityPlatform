/**
 * ODPS React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { odpsService } from '../services/odpsService';
import type {
  ODPSProductCreateRequest,
  ODPSWorkflowStatus,
  ODPSLinkRequest,
  ODPSExportParams,
} from '../../../shared/types/odps';

/**
 * Poll workflow status until completion or failure
 */
export function useODPSWorkflowStatus(
  workflowInstanceId: string | null,
  options: {
    enabled?: boolean;
    refetchInterval?: number | false;
  } = {}
) {
  return useQuery<ODPSWorkflowStatus>({
    queryKey: ['odps', 'workflow', workflowInstanceId],
    queryFn: () => odpsService.getWorkflowStatus(workflowInstanceId!),
    enabled: !!workflowInstanceId && (options.enabled !== false),
    refetchInterval: (query) => {
      const data = query.state.data;
      // Stop polling when workflow is completed or failed
      if (data?.status === 'COMPLETED' || data?.status === 'FAILED') {
        return false;
      }
      return options.refetchInterval ?? 2000; // Poll every 2 seconds by default
    },
  });
}

/**
 * Create ODPS product
 */
export function useCreateODPSProduct() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: ODPSProductCreateRequest) => odpsService.createProduct(data),
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
      odpsService.linkODPS(odcsContractId, data),
    successMessage: 'ODPS linked',
    errorMessage: 'Failed to link ODPS',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', variables.odcsContractId] });
      queryClient.invalidateQueries({ queryKey: ['odps', 'links', variables.odcsContractId] });
    },
  });
}

/**
 * Unlink ODPS from ODCS contract
 */
export function useUnlinkODPS() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (odcsContractId: string) => odpsService.unlinkODPS(odcsContractId),
    successMessage: 'ODPS unlinked',
    errorMessage: 'Failed to unlink ODPS',
    onSuccess: (_, odcsContractId) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', odcsContractId] });
      queryClient.invalidateQueries({ queryKey: ['odps', 'links', odcsContractId] });
    },
  });
}

/**
 * Get contract links (ODPS <-> ODCS)
 */
export function useODPSLinks(contractId: string | null) {
  return useQuery({
    queryKey: ['odps', 'links', contractId],
    queryFn: async () => {
      const data = await odpsService.getLinks(contractId!);
      if (data === undefined) {
        return { odps_link: null, odcs_link: null };
      }
      return data;
    },
    enabled: !!contractId,
  });
}

/**
 * Export ODPS contract
 */
export function useExportODPS() {
  return useMutationWithNotification({
    mutationFn: ({ contractId, params }: { contractId: string; params?: ODPSExportParams }) =>
      odpsService.exportODPS(contractId, params),
    successMessage: 'ODPS exported',
    errorMessage: 'Failed to export ODPS',
  });
}

/**
 * Download ODPS contract
 */
export function useDownloadODPS() {
  return useMutationWithNotification({
    mutationFn: ({ contractId, params }: { contractId: string; params?: ODPSExportParams }) =>
      odpsService.downloadODPS(contractId, params),
    successMessage: 'ODPS downloaded',
    errorMessage: 'Failed to download ODPS',
  });
}
