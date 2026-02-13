/**
 * Developer Portal React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import { developerService } from '../services/developerService';
import type { DeveloperListFilters } from '../../../shared/types/developer';

export function usePlugins(filters: DeveloperListFilters = {}) {
  return useQuery({
    queryKey: ['developer', 'plugins', filters],
    queryFn: () => developerService.listPlugins(filters),
  });
}

export function usePlugin(id: string | null) {
  return useQuery({
    queryKey: ['developer', 'plugins', 'detail', id],
    queryFn: () => developerService.getPlugin(id!),
    enabled: !!id,
  });
}

export function useSDKDocumentation(filters: DeveloperListFilters = {}) {
  return useQuery({
    queryKey: ['developer', 'sdk', filters],
    queryFn: () => developerService.listSDKDocumentation(filters),
  });
}

export function useSDKDoc(id: string | null) {
  return useQuery({
    queryKey: ['developer', 'sdk', 'detail', id],
    queryFn: () => developerService.getSDKDocumentation(id!),
    enabled: !!id,
  });
}
