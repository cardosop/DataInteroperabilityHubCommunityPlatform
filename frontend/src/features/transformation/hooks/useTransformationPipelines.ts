/**
 * Transformation Pipelines React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import { transformationService } from '../services/transformationService';

export function useTransformationPipelines() {
  return useQuery({
    queryKey: ['transformation', 'pipelines'],
    queryFn: () => transformationService.list(),
  });
}

export function useTransformationPipeline(id: string | null) {
  return useQuery({
    queryKey: ['transformation', 'pipelines', id],
    queryFn: () => transformationService.getById(id!),
    enabled: !!id,
  });
}
