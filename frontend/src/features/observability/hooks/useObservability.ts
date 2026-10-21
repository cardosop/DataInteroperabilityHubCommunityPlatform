/**
 * Observability React Query hooks
 */

import { useQuery } from '@tanstack/react-query';
import type {
  ObservabilityFreshnessFilters,
  ObservabilityIncidentsFilters,
  ObservabilitySlasFilters,
  ObservabilityVolumeFilters,
} from '../../../shared/types/observability';
import { observabilityService } from '../services/observabilityService';

export function useFreshnessDashboard(filters: ObservabilityFreshnessFilters = {}) {
  return useQuery({
    queryKey: ['observability', 'freshness', filters],
    queryFn: () => observabilityService.getFreshnessDashboard(filters),
  });
}

export function useVolumeDashboard(filters: ObservabilityVolumeFilters = {}) {
  return useQuery({
    queryKey: ['observability', 'volume', filters],
    queryFn: () => observabilityService.getVolumeDashboard(filters),
  });
}

export function useSlasDashboard(filters: ObservabilitySlasFilters = {}) {
  return useQuery({
    queryKey: ['observability', 'slas', filters],
    queryFn: () => observabilityService.getSlasDashboard(filters),
  });
}

export function useIncidentsDashboard(filters: ObservabilityIncidentsFilters = {}) {
  return useQuery({
    queryKey: ['observability', 'incidents', filters],
    queryFn: () => observabilityService.getIncidentsDashboard(filters),
  });
}
