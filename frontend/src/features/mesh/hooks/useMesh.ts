/**
 * Mesh Hooks
 * React Query hooks for mesh domain operations
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { meshService } from '../services/meshService';
import type {
  MeshDomainCreateRequest,
  MeshDomainUpdateRequest,
  MeshDomainListFilters,
  ApplyPolicyRequest,
  CheckComplianceRequest,
} from '../../../shared/types/mesh';

const QUERY_KEYS = {
  domains: ['mesh', 'domains'] as const,
  domain: (id: string) => ['mesh', 'domains', id] as const,
  domainAnalytics: (id: string) => ['mesh', 'domains', id, 'analytics'] as const,
  topology: ['mesh', 'topology'] as const,
  domainTopology: (id: string) => ['mesh', 'topology', id] as const,
  meshHealth: ['mesh', 'health'] as const,
  domainRelationships: ['mesh', 'relationships'] as const,
  domainPolicies: (id: string) => ['mesh', 'domains', id, 'policies'] as const,
  complianceReports: (id: string) => ['mesh', 'domains', id, 'compliance'] as const,
};

/**
 * Hook to list mesh domains
 */
export function useMeshDomains(filters: MeshDomainListFilters = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.domains, filters],
    queryFn: () => meshService.listDomains(filters),
  });
}

/**
 * Hook to get a single mesh domain
 */
export function useMeshDomain(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.domain(id!),
    queryFn: () => meshService.getDomainById(id!),
    enabled: !!id,
  });
}

/**
 * Hook to create a mesh domain
 */
export function useCreateMeshDomain() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: MeshDomainCreateRequest) => meshService.createDomain(data),
    successMessage: 'Mesh domain created',
    errorMessage: 'Failed to create mesh domain',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domains });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.topology });
    },
  });
}

/**
 * Hook to update a mesh domain
 */
export function useUpdateMeshDomain() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: MeshDomainUpdateRequest }) =>
      meshService.updateDomain(id, data),
    successMessage: 'Mesh domain updated',
    errorMessage: 'Failed to update mesh domain',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domains });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domain(variables.id) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.topology });
    },
  });
}

/**
 * Hook to patch a mesh domain
 */
export function usePatchMeshDomain() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: Partial<MeshDomainUpdateRequest> }) =>
      meshService.patchDomain(id, data),
    successMessage: 'Mesh domain updated',
    errorMessage: 'Failed to update mesh domain',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domains });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domain(variables.id) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.topology });
    },
  });
}

/**
 * Hook to delete a mesh domain
 */
export function useDeleteMeshDomain() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => meshService.deleteDomain(id),
    successMessage: 'Mesh domain deleted',
    errorMessage: 'Failed to delete mesh domain',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domains });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.topology });
    },
  });
}

/**
 * Hook to get domain analytics
 */
export function useDomainAnalytics(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.domainAnalytics(id!),
    queryFn: () => meshService.getDomainAnalytics(id!),
    enabled: !!id,
  });
}

/**
 * Hook to get mesh topology
 */
export function useMeshTopology(includeHealthMetrics: boolean = false) {
  return useQuery({
    queryKey: [...QUERY_KEYS.topology, includeHealthMetrics],
    queryFn: () => meshService.getTopology(includeHealthMetrics),
  });
}

/**
 * Hook to get domain-specific topology
 */
export function useDomainTopology(id: string | undefined, includeHealthMetrics: boolean = true) {
  return useQuery({
    queryKey: [...QUERY_KEYS.domainTopology(id!), includeHealthMetrics],
    queryFn: () => meshService.getDomainTopology(id!, includeHealthMetrics),
    enabled: !!id,
  });
}

/**
 * Hook to get mesh health
 */
export function useMeshHealth() {
  return useQuery({
    queryKey: QUERY_KEYS.meshHealth,
    queryFn: () => meshService.getMeshHealth(),
  });
}

/**
 * Hook to get domain relationships
 */
export function useDomainRelationships() {
  return useQuery({
    queryKey: QUERY_KEYS.domainRelationships,
    queryFn: () => meshService.getDomainRelationships(),
  });
}

/**
 * Hook to list domain policies
 */
export function useDomainPolicies(domainId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.domainPolicies(domainId!),
    queryFn: () => meshService.listDomainPolicies(domainId!),
    enabled: !!domainId,
  });
}

/**
 * Hook to apply a policy to a domain
 */
export function useApplyPolicy() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ domainId, data }: { domainId: string; data: ApplyPolicyRequest }) =>
      meshService.applyPolicy(domainId, data),
    successMessage: 'Policy applied',
    errorMessage: 'Failed to apply policy',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domainPolicies(variables.domainId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domain(variables.domainId) });
    },
  });
}

/**
 * Hook to remove a policy from a domain
 */
export function useRemovePolicy() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ domainId, policyId }: { domainId: string; policyId: string }) =>
      meshService.removePolicy(domainId, policyId),
    successMessage: 'Policy removed',
    errorMessage: 'Failed to remove policy',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domainPolicies(variables.domainId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domain(variables.domainId) });
    },
  });
}

/**
 * Hook to check compliance for a domain
 */
export function useCheckCompliance() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ domainId, data }: { domainId: string; data?: CheckComplianceRequest }) =>
      meshService.checkCompliance(domainId, data),
    successMessage: 'Compliance checked',
    errorMessage: 'Failed to check compliance',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.complianceReports(variables.domainId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domain(variables.domainId) });
    },
  });
}

/**
 * Hook to list compliance reports for a domain
 */
export function useComplianceReports(domainId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.complianceReports(domainId!),
    queryFn: () => meshService.listComplianceReports(domainId!),
    enabled: !!domainId,
  });
}

/**
 * Hook to transfer domain ownership
 */
export function useTransferOwnership() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ domainId, newOwnerId }: { domainId: string; newOwnerId: string | null }) =>
      meshService.transferOwnership(domainId, newOwnerId),
    successMessage: 'Ownership transferred',
    errorMessage: 'Failed to transfer ownership',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domain(variables.domainId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.domains });
    },
  });
}
