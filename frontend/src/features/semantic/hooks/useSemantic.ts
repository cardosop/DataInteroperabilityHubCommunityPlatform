/**
 * Semantic React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type {
  SPARQLQueryRequest,
  SemanticResourceListFilters,
} from '../../../shared/types/semantic';
import { semanticService } from '../services/semanticService';

export function useSPARQLQuery() {
  return useMutationWithNotification({
    mutationFn: (data: SPARQLQueryRequest) => semanticService.querySPARQL(data),
    successMessage: 'SPARQL query executed',
    errorMessage: 'Failed to execute SPARQL query',
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

/**
 * Phase 230.5.5 (REQ-SEM-RELATIONSHIPS-001) — fetch RDF
 * relationships for a contract via the Django route.
 *
 * The Django route is tenant-scoped; cross-tenant contract ids
 * surface as 404 from the underlying ``apiClient``.
 */
export function useContractRelationships(contractId: string | null) {
  return useQuery({
    queryKey: ['semantic', 'contract-relationships', contractId],
    queryFn: () => semanticService.getContractRelationships(contractId!),
    enabled: !!contractId,
    staleTime: 60_000, // Mirror the server's 60s Redis cache.
  });
}

export function useSemanticResources(filters: SemanticResourceListFilters = {}) {
  return useQuery({
    queryKey: ['semantic', 'resources', 'list', filters],
    queryFn: () => semanticService.listResources(filters),
  });
}
