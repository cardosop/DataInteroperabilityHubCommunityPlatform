/**
 * Virtualization Hooks
 * React Query hooks for virtual dataset and query execution operations
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { virtualizationService } from '../services/virtualizationService';
import type {
  VirtualDatasetCreateRequest,
  VirtualDatasetUpdateRequest,
  VirtualDatasetListFilters,
  QueryExecutionCreateRequest,
  QueryExecutionListFilters,
} from '../../../shared/types/virtualization';

const QUERY_KEYS = {
  datasets: ['virtualization', 'datasets'] as const,
  dataset: (id: string) => ['virtualization', 'datasets', id] as const,
  datasetVersions: (id: string) => ['virtualization', 'datasets', id, 'versions'] as const,
  queryExecutions: ['virtualization', 'queries'] as const,
  queryExecution: (id: string) => ['virtualization', 'queries', id] as const,
  queryExecutionProgress: (id: string) => ['virtualization', 'queries', id, 'progress'] as const,
  queryExecutionResult: (id: string) => ['virtualization', 'queries', id, 'result'] as const,
};

/**
 * Hook to list virtual datasets
 */
export function useVirtualDatasets(filters: VirtualDatasetListFilters = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.datasets, filters],
    queryFn: () => virtualizationService.listDatasets(filters),
  });
}

/**
 * Hook to get a single virtual dataset
 */
export function useVirtualDataset(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.dataset(id!),
    queryFn: () => virtualizationService.getDatasetById(id!),
    enabled: !!id,
  });
}

/**
 * Hook to create a virtual dataset
 */
export function useCreateVirtualDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: VirtualDatasetCreateRequest) => virtualizationService.createDataset(data),
    successMessage: 'Virtual dataset created',
    errorMessage: 'Failed to create virtual dataset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets });
    },
  });
}

/**
 * Hook to update a virtual dataset
 */
export function useUpdateVirtualDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: VirtualDatasetUpdateRequest }) =>
      virtualizationService.updateDataset(id, data),
    successMessage: 'Virtual dataset updated',
    errorMessage: 'Failed to update virtual dataset',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dataset(variables.id) });
    },
  });
}

/**
 * Hook to patch a virtual dataset
 */
export function usePatchVirtualDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: Partial<VirtualDatasetUpdateRequest> }) =>
      virtualizationService.patchDataset(id, data),
    successMessage: 'Virtual dataset updated',
    errorMessage: 'Failed to update virtual dataset',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dataset(variables.id) });
    },
  });
}

/**
 * Hook to delete a virtual dataset
 */
export function useDeleteVirtualDataset() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => virtualizationService.deleteDataset(id),
    successMessage: 'Virtual dataset deleted',
    errorMessage: 'Failed to delete virtual dataset',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets });
    },
  });
}

/**
 * Hook to validate a virtual dataset
 */
export function useValidateVirtualDataset() {
  return useMutationWithNotification({
    mutationFn: (id: string) => virtualizationService.validateDataset(id),
    successMessage: 'Virtual dataset validated',
    errorMessage: 'Validation failed',
  });
}

/**
 * Hook to get dataset versions
 */
export function useDatasetVersions(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.datasetVersions(id!),
    queryFn: () => virtualizationService.getDatasetVersions(id!),
    enabled: !!id,
  });
}

/**
 * Hook to execute a query on a virtual dataset
 */
export function useExecuteQuery() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ datasetId, data }: { datasetId: string; data: QueryExecutionCreateRequest }) =>
      virtualizationService.executeQuery(datasetId, data),
    successMessage: 'Query executed',
    errorMessage: 'Failed to execute query',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.queryExecutions });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dataset(variables.datasetId) });
    },
  });
}

/**
 * Hook to list query executions
 */
export function useQueryExecutions(filters: QueryExecutionListFilters = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.queryExecutions, filters],
    queryFn: () => virtualizationService.listQueryExecutions(filters),
  });
}

/**
 * Hook to get a single query execution
 */
export function useQueryExecution(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.queryExecution(id!),
    queryFn: () => virtualizationService.getQueryExecutionById(id!),
    enabled: !!id,
  });
}

/**
 * Hook to cancel a query execution
 */
export function useCancelQueryExecution() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => virtualizationService.cancelQueryExecution(id),
    successMessage: 'Query execution cancelled',
    errorMessage: 'Failed to cancel query execution',
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.queryExecution(id) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.queryExecutions });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.queryExecutionProgress(id) });
    },
  });
}

/**
 * Hook to get query execution progress (with polling)
 */
export function useQueryExecutionProgress(id: string | undefined, enabled: boolean = true) {
  return useQuery({
    queryKey: QUERY_KEYS.queryExecutionProgress(id!),
    queryFn: () => virtualizationService.getQueryExecutionProgress(id!),
    enabled: !!id && enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      // Poll every 2 seconds if query is running
      if (data?.status === 'RUNNING' || data?.status === 'PENDING') {
        return 2000;
      }
      return false;
    },
  });
}

/**
 * Hook to get query execution result
 */
export function useQueryExecutionResult(
  id: string | undefined,
  page?: number,
  pageSize?: number,
  format: 'json' | 'csv' | 'parquet' = 'json'
) {
  return useQuery({
    queryKey: [...QUERY_KEYS.queryExecutionResult(id!), page, pageSize, format],
    queryFn: () => virtualizationService.getQueryExecutionResult(id!, page, pageSize, format),
    enabled: !!id,
  });
}
