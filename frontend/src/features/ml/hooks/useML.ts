/**
 * ML/ODH React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

  return useMutation({
    mutationFn: (data: MLModelCreateRequest) => mlService.createModel(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
    },
  });
}

export function useUpdateMLModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MLModelUpdateRequest }) =>
      mlService.updateModel(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
      queryClient.invalidateQueries({ queryKey: ['ml', 'models', 'detail', variables.id] });
    },
  });
}

export function useDeleteMLModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => mlService.deleteModel(id),
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

  return useMutation({
    mutationFn: (data: TrainingJobSubmitRequest) => mlService.submitTrainingJob(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'training', 'jobs'] });
    },
  });
}

export function useCancelTrainingJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => mlService.cancelTrainingJob(id),
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

  return useMutation({
    mutationFn: (data: InferenceDeployRequest) => mlService.deployInference(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'inference', 'deployments'] });
    },
  });
}

export function useUndeployInference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => mlService.undeployInference(id),
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
