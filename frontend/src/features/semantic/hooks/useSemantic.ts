/**
 * Semantic React Query Hooks
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import type {
  SPARQLQueryRequest,
  SemanticResourceListFilters,
} from '../../../shared/types/semantic';
import { semanticService } from '../services/semanticService';

export function useSPARQLQuery() {
  return useMutation({
    mutationFn: (data: SPARQLQueryRequest) => semanticService.querySPARQL(data),
  });
}

export function useResolveURI(resourceType: string | null, resourceId: string | null) {
  return useQuery({
    queryKey: ['semantic', 'uri', resourceType, resourceId],
    queryFn: () => semanticService.resolveURI(resourceType!, resourceId!),
    enabled: !!resourceType && !!resourceId,
  });
}

export function useResolveFieldURI(assetUuid: string | null, fieldName: string | null) {
  return useQuery({
    queryKey: ['semantic', 'field-uri', assetUuid, fieldName],
    queryFn: () => semanticService.resolveFieldURI(assetUuid!, fieldName!),
    enabled: !!assetUuid && !!fieldName,
  });
}

export function useOntology() {
  return useQuery({
    queryKey: ['semantic', 'ontology'],
    queryFn: () => semanticService.getOntology(),
    staleTime: 3600000, // Cache for 1 hour (ontology rarely changes)
  });
}

export function useJSONLDContext() {
  return useQuery({
    queryKey: ['semantic', 'context'],
    queryFn: () => semanticService.getJSONLDContext(),
    staleTime: 300000, // Cache for 5 minutes
  });
}

export function useSemanticResources(filters: SemanticResourceListFilters = {}) {
  return useQuery({
    queryKey: ['semantic', 'resources', 'list', filters],
    queryFn: () => semanticService.listResources(filters),
  });
}
