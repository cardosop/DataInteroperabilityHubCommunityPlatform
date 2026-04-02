/**
 * Listings React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { listingService } from '../services/listingService';
import type {
  ListingCreateRequest,
  ListingUpdateRequest,
  ListingListFilters,
} from '../../../shared/types/marketplace';

export function useListings(filters: ListingListFilters = {}) {
  return useQuery({
    queryKey: ['marketplace', 'listings', 'list', filters],
    queryFn: async () => {
      const data = await listingService.list(filters);
      if (data === undefined) {
        return { results: [], count: 0 };
      }
      return data;
    },
  });
}

export function useSearchListings(query: string, filters: ListingListFilters = {}) {
  return useQuery({
    queryKey: ['marketplace', 'listings', 'search', query, filters],
    queryFn: async () => {
      const data = await listingService.search(query, filters);
      if (data === undefined) {
        return { results: [], count: 0 };
      }
      return data;
    },
    enabled: !!query && query.length > 0,
  });
}

export function useListing(id: string | null) {
  return useQuery({
    queryKey: ['marketplace', 'listings', 'detail', id],
    queryFn: () => listingService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateListing() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: ListingCreateRequest) => listingService.create(data),
    successMessage: 'Listing created',
    errorMessage: 'Failed to create listing',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'listings'] });
    },
  });
}

export function useUpdateListing() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: ListingUpdateRequest }) =>
      listingService.update(id, data),
    successMessage: 'Listing updated',
    errorMessage: 'Failed to update listing',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'listings'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'listings', 'detail', variables.id] });
    },
  });
}

export function useDeleteListing() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => listingService.delete(id),
    successMessage: 'Listing deleted',
    errorMessage: 'Failed to delete listing',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'listings'] });
    },
  });
}

export function useDownloadListing() {
  return useMutationWithNotification({
    mutationFn: (id: string) => listingService.download(id),
    successMessage: 'Listing downloaded',
    errorMessage: 'Failed to download listing',
  });
}

export function usePreviewListing() {
  return useMutationWithNotification({
    mutationFn: ({ id, format }: { id: string; format?: string }) => listingService.preview(id, format),
    successMessage: 'Listing preview loaded',
    errorMessage: 'Failed to preview listing',
  });
}
