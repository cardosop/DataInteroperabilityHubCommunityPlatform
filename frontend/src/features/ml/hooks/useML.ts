/**
 * ML/ODH React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { mlService } from '../services/mlService';
import type {
  MLModelCreateRequest,
  MLModelUpdateRequest,
  TrainingJobSubmitRequest,
  InferenceDeployRequest,
  MLListFilters,
} from '../../../shared/types/ml';

export function useMLModels(filters: MLListFilters = {}) {
  return useQuery({
    queryKey: ['ml', 'models', filters],
    queryFn: () => mlService.listModels(filters),
  });
}

export function useMLModel(id: string | null) {
  return useQuery({
    queryKey: ['ml', 'models', 'detail', id],
    queryFn: () => mlService.getModel(id!),
    enabled: !!id,
  });
}

export function useCreateMLModel() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: MLModelCreateRequest) => mlService.createModel(data),
    successMessage: 'ML model created',
    errorMessage: 'Failed to create ML model',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
    },
  });
}

export function useUpdateMLModel() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: MLModelUpdateRequest }) =>
      mlService.updateModel(id, data),
    successMessage: 'ML model updated',
    errorMessage: 'Failed to update ML model',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
      queryClient.invalidateQueries({ queryKey: ['ml', 'models', 'detail', variables.id] });
    },
  });
}

export function useDeleteMLModel() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => mlService.deleteModel(id),
    successMessage: 'ML model deleted',
    errorMessage: 'Failed to delete ML model',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
    },
  });
}

export function useTrainingJobs(filters: MLListFilters = {}) {
  return useQuery({
    queryKey: ['ml', 'training', 'jobs', filters],
    queryFn: () => mlService.listTrainingJobs(filters),
  });
}

export function useTrainingJob(id: string | null) {
  return useQuery({
    queryKey: ['ml', 'training', 'jobs', 'detail', id],
    queryFn: () => mlService.getTrainingJob(id!),
    enabled: !!id,
  });
}

export function useSubmitTrainingJob() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: TrainingJobSubmitRequest) => mlService.submitTrainingJob(data),
    successMessage: 'Training job submitted',
    errorMessage: 'Failed to submit training job',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'training', 'jobs'] });
    },
  });
}

export function useCancelTrainingJob() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => mlService.cancelTrainingJob(id),
    successMessage: 'Training job cancelled',
    errorMessage: 'Failed to cancel training job',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'training', 'jobs'] });
    },
  });
}

export function useInferenceDeployments(filters: MLListFilters = {}) {
  return useQuery({
    queryKey: ['ml', 'inference', 'deployments', filters],
    queryFn: () => mlService.listInferenceDeployments(filters),
  });
}

export function useInferenceDeployment(id: string | null) {
  return useQuery({
    queryKey: ['ml', 'inference', 'deployments', 'detail', id],
    queryFn: () => mlService.getInferenceDeployment(id!),
    enabled: !!id,
  });
}

export function useDeployInference() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: InferenceDeployRequest) => mlService.deployInference(data),
    successMessage: 'Inference deployed',
    errorMessage: 'Failed to deploy inference',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'inference', 'deployments'] });
    },
  });
}

export function useUndeployInference() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => mlService.undeployInference(id),
    successMessage: 'Inference undeployed',
    errorMessage: 'Failed to undeploy inference',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'inference', 'deployments'] });
    },
  });
}

export function useInferenceMetrics(id: string | null, startTime?: string, endTime?: string) {
  return useQuery({
    queryKey: ['ml', 'inference', 'deployments', id, 'metrics', startTime, endTime],
    queryFn: () => mlService.getInferenceMetrics(id!, startTime, endTime),
    enabled: !!id,
  });
}
