/**
 * Phase 278.H.4 — Saved searches React Query hooks.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { savedSearchService } from '../services/savedSearchService';
import type {
  SavedSearchCreateRequest,
  SavedSearchUpdateRequest,
} from '../../../shared/types/marketplace';

const QUERY_KEY = ['marketplace', 'saved-searches'] as const;

export function useSavedSearches() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => savedSearchService.list(),
    staleTime: 60 * 1000,
  });
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: SavedSearchCreateRequest) => savedSearchService.create(data),
    successMessage: 'Search saved',
    errorMessage: 'Failed to save search',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useUpdateSavedSearch() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: SavedSearchUpdateRequest }) =>
      savedSearchService.update(id, data),
    successMessage: 'Saved search updated',
    errorMessage: 'Failed to update saved search',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => savedSearchService.delete(id),
    successMessage: 'Saved search removed',
    errorMessage: 'Failed to remove saved search',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}
