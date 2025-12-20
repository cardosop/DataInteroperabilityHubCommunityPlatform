/**
 * Asset API Hooks
 *
 * React Query hooks for asset management operations:
 * - useAssets() - List assets query
 * - useAsset(id) - Get single asset query
 * - useCreateAsset() - Create asset mutation
 * - useUpdateAsset() - Update asset mutation
 * - useDeleteAsset() - Delete asset mutation
 *
 * These hooks provide:
 * - Automatic caching and background updates
 * - Request deduplication
 * - Optimistic updates
 * - Error handling and retry logic
 * - Query invalidation on mutations
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query'
import {
  listAssets,
  getAsset,
  createAsset,
  updateAsset,
  deleteAsset,
  type Asset,
  type ListAssetsParams,
  type ListAssetsResponse,
  type CreateAssetRequest,
  type UpdateAssetRequest,
} from '@/lib/api/assets'
import { queryKeys, invalidateQueries } from '@/lib/api/react-query'

/**
 * useAssets Hook
 *
 * Query hook for listing assets with filtering, sorting, and pagination.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Query result with assets list
 *
 * @example
 * ```tsx
 * function AssetsList() {
 *   const { data, isLoading, error } = useAssets({
 *     page: 1,
 *     page_size: 20,
 *     status: 'ACTIVE',
 *     search: 'customer'
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(asset => (
 *         <AssetCard key={asset.id} asset={asset} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useAssets(
  params?: ListAssetsParams,
  options?: Omit<UseQueryOptions<ListAssetsResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<ListAssetsResponse, Error>({
    queryKey: queryKeys.assets.list(params),
    queryFn: () => listAssets(params),
    ...options,
  })
}

/**
 * useAsset Hook
 *
 * Query hook for getting a single asset by ID.
 *
 * @param id - Asset UUID
 * @param options - Additional React Query options
 * @returns Query result with asset details
 *
 * @example
 * ```tsx
 * function AssetDetail({ assetId }: { assetId: string }) {
 *   const { data: asset, isLoading, error } = useAsset(assetId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *   if (!asset) return <NotFound />
 *
 *   return <AssetDetails asset={asset} />
 * }
 * ```
 */
export function useAsset(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Asset, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Asset, Error>({
    queryKey: queryKeys.assets.detail(id!),
    queryFn: () => getAsset(id!),
    enabled: !!id, // Only fetch if ID is provided
    ...options,
  })
}

/**
 * useCreateAsset Hook
 *
 * Mutation hook for creating a new asset.
 * Automatically invalidates asset list queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 *
 * @example
 * ```tsx
 * function CreateAssetForm() {
 *   const createAsset = useCreateAsset()
 *
 *   const handleSubmit = async (data: CreateAssetRequest) => {
 *     try {
 *       const newAsset = await createAsset.mutateAsync(data)
 *       // Navigate to asset detail
 *       navigate(`/assets/${newAsset.id}`)
 *     } catch (error) {
 *       // Handle error
 *       showError(error)
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <button disabled={createAsset.isPending}>
 *         {createAsset.isPending ? 'Creating...' : 'Create Asset'}
 *       </button>
 *     </form>
 *   )
 * }
 * ```
 */
export function useCreateAsset(
  options?: Omit<UseMutationOptions<Asset, Error, CreateAssetRequest>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  // Extract onSuccess and onError from options to avoid overriding our handlers
  const { onSuccess: userOnSuccess, onError: userOnError, ...restOptions } = options || {}

  return useMutation<Asset, Error, CreateAssetRequest>({
    mutationFn: createAsset,
    onSuccess: (data, variables, context) => {
      // Invalidate all asset list queries to refetch with new asset
      invalidateQueries(queryKeys.assets.lists())

      // Optionally set the new asset in cache for immediate access
      queryClient.setQueryData(queryKeys.assets.detail(data.id), data)

      // Call custom onSuccess if provided
      userOnSuccess?.(data, variables, context)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      userOnError?.(error, variables, context)
    },
    ...restOptions,
  })
}

/**
 * useUpdateAsset Hook
 *
 * Mutation hook for updating an existing asset.
 * Automatically invalidates related queries and updates cache on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 *
 * @example
 * ```tsx
 * function EditAssetForm({ assetId }: { assetId: string }) {
 *   const { data: asset } = useAsset(assetId)
 *   const updateAsset = useUpdateAsset()
 *
 *   const handleSubmit = async (data: UpdateAssetRequest) => {
 *     try {
 *       await updateAsset.mutateAsync({
 *         id: assetId,
 *         ...data,
 *         version: asset.version // Include current version for optimistic locking
 *       })
 *       // Show success message
 *       showSuccess('Asset updated successfully')
 *     } catch (error) {
 *       // Handle error
 *       showError(error)
 *     }
 *   }
 *
 *   return <form onSubmit={handleSubmit}><!-- form fields --></form>
 * }
 * ```
 */
export function useUpdateAsset(
  options?: Omit<UseMutationOptions<Asset, Error, { id: string; data: UpdateAssetRequest }>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  // Extract onSuccess and onError from options to avoid overriding our handlers
  const { onSuccess: userOnSuccess, onError: userOnError, ...restOptions } = options || {}

  return useMutation<Asset, Error, { id: string; data: UpdateAssetRequest }>({
    mutationFn: ({ id, data }) => updateAsset(id, data),
    onSuccess: (data, variables, context) => {
      // Invalidate all asset list queries
      invalidateQueries(queryKeys.assets.lists())

      // Update the specific asset in cache
      queryClient.setQueryData(queryKeys.assets.detail(data.id), data)

      // Call custom onSuccess if provided
      userOnSuccess?.(data, variables, context)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      userOnError?.(error, variables, context)
    },
    ...restOptions,
  })
}

/**
 * useDeleteAsset Hook
 *
 * Mutation hook for deleting an asset.
 * Automatically invalidates related queries and removes from cache on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 *
 * @example
 * ```tsx
 * function DeleteAssetButton({ assetId }: { assetId: string }) {
 *   const deleteAsset = useDeleteAsset()
 *   const navigate = useNavigate()
 *
 *   const handleDelete = async () => {
 *     if (!confirm('Are you sure you want to delete this asset?')) {
 *       return
 *     }
 *
 *     try {
 *       await deleteAsset.mutateAsync(assetId)
 *       // Navigate to assets list
 *       navigate('/assets')
 *       showSuccess('Asset deleted successfully')
 *     } catch (error) {
 *       // Handle error
 *       showError(error)
 *     }
 *   }
 *
 *   return (
 *     <button onClick={handleDelete} disabled={deleteAsset.isPending}>
 *       {deleteAsset.isPending ? 'Deleting...' : 'Delete Asset'}
 *     </button>
 *   )
 * }
 * ```
 */
export function useDeleteAsset(
  options?: Omit<UseMutationOptions<void, Error, string>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  // Extract onSuccess and onError from options to avoid overriding our handlers
  const { onSuccess: userOnSuccess, onError: userOnError, ...restOptions } = options || {}

  return useMutation<void, Error, string>({
    mutationFn: deleteAsset,
    onSuccess: (data, assetId, context) => {
      // Invalidate all asset list queries
      invalidateQueries(queryKeys.assets.lists())

      // Remove the deleted asset from cache
      queryClient.removeQueries({ queryKey: queryKeys.assets.detail(assetId) })

      // Call custom onSuccess if provided
      userOnSuccess?.(data, assetId, context)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      userOnError?.(error, variables, context)
    },
    ...restOptions,
  })
}

