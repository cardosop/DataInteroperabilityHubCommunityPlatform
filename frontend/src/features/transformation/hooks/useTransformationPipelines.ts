/**
 * Transformation Pipelines React Query Hooks — Phase 115D.1
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { transformationService } from '../services/transformationService';
import type {
  TransformationListFilters,
  TransformationPipelineCreateRequest,
  TransformationPipelineUpdateRequest,
  PipelineExecuteRequest,
} from '../../../shared/types/transformation';

export function useTransformationPipelines(
  filters: TransformationListFilters = {},
) {
  return useQuery({
    queryKey: ['transformation', 'pipelines', filters],
    queryFn: () => transformationService.list(filters),
  });
}

export function useTransformationPipeline(id: string | null) {
  return useQuery({
    queryKey: ['transformation', 'pipelines', 'detail', id],
    queryFn: () => transformationService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateTransformationPipeline() {
  const qc = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: TransformationPipelineCreateRequest) =>
      transformationService.create(data),
    successMessage: 'Pipeline created',
    errorMessage: 'Failed to create pipeline',
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transformation', 'pipelines'] });
    },
  });
}

export function useUpdateTransformationPipeline() {
  const qc = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: TransformationPipelineUpdateRequest }) =>
      transformationService.update(id, data),
    successMessage: 'Pipeline updated',
    errorMessage: 'Failed to update pipeline',
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['transformation', 'pipelines'] });
      qc.invalidateQueries({
        queryKey: ['transformation', 'pipelines', 'detail', vars.id],
      });
    },
  });
}

export function useDeleteTransformationPipeline() {
  const qc = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => transformationService.remove(id),
    successMessage: 'Pipeline deleted',
    errorMessage: 'Failed to delete pipeline',
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transformation', 'pipelines'] });
    },
  });
}

export function useExecuteTransformationPipeline() {
  const qc = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: PipelineExecuteRequest }) =>
      transformationService.execute(id, data),
    successMessage: 'Pipeline execution started',
    errorMessage: 'Failed to execute pipeline',
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transformation', 'executions'] });
    },
  });
}

export function useTransformationExecutions(
  filters: TransformationListFilters = {},
) {
  return useQuery({
    queryKey: ['transformation', 'executions', filters],
    queryFn: () => transformationService.listExecutions(filters),
  });
}

export function useTransformationExecution(id: string | null) {
  return useQuery({
    queryKey: ['transformation', 'executions', 'detail', id],
    queryFn: () => transformationService.getExecution(id!),
    enabled: !!id,
  });
}
