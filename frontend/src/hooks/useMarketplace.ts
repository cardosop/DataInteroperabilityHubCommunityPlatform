/**
 * Marketplace API Hooks
 *
 * React Query hooks for marketplace operations:
 * - useMarketplaceContracts() - Search contracts query
 * - useDownloadContract() - Download contract mutation
 *
 * These hooks provide:
 * - Automatic caching and background updates
 * - Request deduplication
 * - Error handling and retry logic
 * - Query invalidation on mutations
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from '@tanstack/react-query'
import {
  searchMarketplaceContracts,
  downloadMarketplaceContract,
  getMarketplaceListing,
  getMarketplaceListingPreview,
  createMarketplaceOrder,
  type SearchMarketplaceContractsParams,
  type SearchMarketplaceContractsResponse,
  type DownloadContractParams,
  type DownloadContractResponse,
  type MarketplaceListing,
  type ListingPreviewResponse,
  type CreateOrderRequest,
  type CreateOrderResponse,
} from '@/lib/api/marketplace'
import { queryKeys, invalidateQueries } from '@/lib/api/react-query'

/**
 * useMarketplaceContracts Hook
 *
 * Query hook for searching contracts in the marketplace.
 * Only returns published listings from verified tenants.
 *
 * @param params - Query parameters for search and filtering
 * @param options - Additional React Query options
 * @returns Query result with marketplace listings
 *
 * @example
 * ```tsx
 * function MarketplaceSearch() {
 *   const { data, isLoading, error } = useMarketplaceContracts({
 *     search: 'customer data',
 *     domain: 'marketing',
 *     tags: ['analytics'],
 *     page: 1,
 *     page_size: 20
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(listing => (
 *         <ListingCard key={listing.id} listing={listing} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useMarketplaceContracts(
  params?: SearchMarketplaceContractsParams,
  options?: Omit<
    UseQueryOptions<SearchMarketplaceContractsResponse, Error>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery<SearchMarketplaceContractsResponse, Error>({
    queryKey: queryKeys.marketplace.contracts.search(params),
    queryFn: () => searchMarketplaceContracts(params),
    ...options,
  })
}

/**
 * useDownloadContract Hook
 *
 * Mutation hook for downloading a contract from a marketplace listing.
 * Requires active entitlement for cross-tenant access.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 *
 * @example
 * ```tsx
 * function ContractDownloadButton({ listingId }: { listingId: string }) {
 *   const downloadContract = useDownloadContract({
 *     onSuccess: (data) => {
 *       // Save file to disk
 *       const blob = new Blob([data.contract_content], {
 *         type: data.format === 'JSON' ? 'application/json' : 'text/plain'
 *       })
 *       const url = URL.createObjectURL(blob)
 *       const a = document.createElement('a')
 *       a.href = url
 *       a.download = data.filename
 *       a.click()
 *       URL.revokeObjectURL(url)
 *     },
 *     onError: (error) => {
 *       showError('Failed to download contract: ' + error.message)
 *     }
 *   })
 *
 *   const handleDownload = () => {
 *     downloadContract.mutate({
 *       listingId,
 *       format: 'original'
 *     })
 *   }
 *
 *   return (
 *     <button
 *       onClick={handleDownload}
 *       disabled={downloadContract.isPending}
 *     >
 *       {downloadContract.isPending ? 'Downloading...' : 'Download Contract'}
 *     </button>
 *   )
 * }
 * ```
 */
export function useDownloadContract(
  options?: Omit<
    UseMutationOptions<DownloadContractResponse, Error, DownloadContractParams>,
    'mutationFn' | 'onSuccess'
  >
) {
  const queryClient = useQueryClient()

  return useMutation<DownloadContractResponse, Error, DownloadContractParams>({
    mutationFn: (params: DownloadContractParams) =>
      downloadMarketplaceContract(params),
    onSuccess: (data, variables) => {
      // Invalidate marketplace search queries to refresh listing data
      invalidateQueries(queryKeys.marketplace.contracts.all)

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    ...options,
  })
}

/**
 * useMarketplaceListing Hook
 *
 * Query hook for getting a single marketplace listing by ID.
 *
 * @param id - Listing UUID
 * @param options - Additional React Query options
 * @returns Query result with listing details
 */
export function useMarketplaceListing(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<MarketplaceListing, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<MarketplaceListing, Error>({
    queryKey: queryKeys.marketplace.listing(id!),
    queryFn: () => getMarketplaceListing(id!),
    enabled: !!id,
    ...options,
  })
}

/**
 * useMarketplaceListingPreview Hook
 *
 * Query hook for getting marketplace listing preview (asset, dataset, quality metrics, schema).
 *
 * @param id - Listing UUID
 * @param options - Additional React Query options
 * @returns Query result with listing preview
 */
export function useMarketplaceListingPreview(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<ListingPreviewResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<ListingPreviewResponse, Error>({
    queryKey: [...queryKeys.marketplace.listing(id!), 'preview'] as const,
    queryFn: () => getMarketplaceListingPreview(id!),
    enabled: !!id,
    ...options,
  })
}

/**
 * useCreateMarketplaceOrder Hook
 *
 * Mutation hook for creating a marketplace order (access request).
 * Automatically invalidates relevant queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useCreateMarketplaceOrder(
  options?: Omit<
    UseMutationOptions<CreateOrderResponse, Error, CreateOrderRequest>,
    'mutationFn' | 'onSuccess'
  >
) {
  const queryClient = useQueryClient()

  return useMutation<CreateOrderResponse, Error, CreateOrderRequest>({
    mutationFn: (data: CreateOrderRequest) => createMarketplaceOrder(data),
    onSuccess: (data, variables) => {
      // Invalidate marketplace queries
      invalidateQueries(queryKeys.marketplace.all)

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    ...options,
  })
}

