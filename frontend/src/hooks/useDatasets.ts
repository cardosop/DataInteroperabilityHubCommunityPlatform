/**
 * Dataset API Hooks
 *
 * React Query hooks for dataset management operations:
 * - useDatasets() - List datasets query
 * - useDataset(id) - Get single dataset query
 * - useCreateDataset() - Create dataset mutation
 * - useUploadDataset() - Upload dataset mutation
 *
 * These hooks provide:
 * - Automatic caching and background updates
 * - Request deduplication
 * - Optimistic updates
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
  listDatasets,
  getDataset,
  createDataset,
  uploadDataset,
  type Dataset,
  type ListDatasetsParams,
  type ListDatasetsResponse,
  type CreateDatasetRequest,
  type UploadDatasetRequest,
} from '@/lib/api/datasets'
import { queryKeys, invalidateQueries } from '@/lib/api/react-query'

/**
 * useDatasets Hook
 *
 * Query hook for listing datasets with filtering, sorting, and pagination.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Query result with datasets list
 *
 * @example
 * ```tsx
 * function DatasetsList() {
 *   const { data, isLoading, error } = useDatasets({
 *     page: 1,
 *     page_size: 20,
 *     format: 'CSV',
 *     asset_id: 'asset-123'
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(dataset => (
 *         <DatasetCard key={dataset.id} dataset={dataset} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useDatasets(
  params?: ListDatasetsParams,
  options?: Omit<UseQueryOptions<ListDatasetsResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<ListDatasetsResponse, Error>({
    queryKey: queryKeys.datasets.list(params),
    queryFn: () => listDatasets(params),
    ...options,
  })
}

/**
 * useDataset Hook
 *
 * Query hook for getting a single dataset by ID.
 *
 * @param id - Dataset UUID
 * @param options - Additional React Query options
 * @returns Query result with dataset details
 *
 * @example
 * ```tsx
 * function DatasetDetail({ datasetId }: { datasetId: string }) {
 *   const { data: dataset, isLoading, error } = useDataset(datasetId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *   if (!dataset) return <NotFound />
 *
 *   return <DatasetDetails dataset={dataset} />
 * }
 * ```
 */
export function useDataset(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Dataset, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Dataset, Error>({
    queryKey: queryKeys.datasets.detail(id!),
    queryFn: () => getDataset(id!),
    enabled: !!id, // Only fetch if ID is provided
    ...options,
  })
}

/**
 * useCreateDataset Hook
 *
 * Mutation hook for creating a new dataset from an uploaded file.
 * Automatically invalidates dataset list queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 *
 * @example
 * ```tsx
 * function CreateDatasetForm() {
 *   const createDataset = useCreateDataset()
 *
 *   const handleSubmit = async (data: CreateDatasetRequest) => {
 *     try {
 *       const newDataset = await createDataset.mutateAsync(data)
 *       // Navigate to dataset detail
 *       navigate(`/datasets/${newDataset.id}`)
 *     } catch (error) {
 *       // Handle error
 *       showError(error)
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <!-- form fields -->
 *     </form>
 *   )
 * }
 * ```
 */
export function useCreateDataset(
  options?: Omit<
    UseMutationOptions<Dataset, Error, CreateDatasetRequest>,
    'mutationFn' | 'onSuccess'
  >
) {
  const queryClient = useQueryClient()

  return useMutation<Dataset, Error, CreateDatasetRequest>({
    mutationFn: (data: CreateDatasetRequest) => createDataset(data),
    onSuccess: (data) => {
      // Invalidate dataset list queries
      invalidateQueries(queryKeys.datasets.lists())

      // Invalidate specific dataset detail query
      invalidateQueries(queryKeys.datasets.detail(data.id))

      // If dataset is attached to an asset, invalidate asset queries
      if (data.asset) {
        invalidateQueries(queryKeys.assets.detail(data.asset))
        invalidateQueries(queryKeys.assets.lists())
      }

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, data as any, undefined as any)
    },
    ...options,
  })
}

/**
 * useUploadDataset Hook
 *
 * Mutation hook for uploading a file and creating a dataset.
 * This combines file upload (init, upload to S3, complete) and dataset creation.
 * Automatically invalidates dataset list queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 *
 * @example
 * ```tsx
 * function UploadDatasetForm() {
 *   const uploadDataset = useUploadDataset()
 *   const [progress, setProgress] = useState(0)
 *
 *   const handleFileSelect = async (file: File) => {
 *     try {
 *       const dataset = await uploadDataset.mutateAsync({
 *         file,
 *         asset_id: 'asset-123',
 *         onProgress: (progress) => setProgress(progress)
 *       })
 *       // Navigate to dataset detail
 *       navigate(`/datasets/${dataset.id}`)
 *     } catch (error) {
 *       // Handle error
 *       showError(error)
 *     }
 *   }
 *
 *   return (
 *     <div>
 *       <input
 *         type="file"
 *         onChange={(e) => {
 *           const file = e.target.files?.[0]
 *           if (file) handleFileSelect(file)
 *         }}
 *       />
 *       {uploadDataset.isPending && (
 *         <ProgressBar value={progress} />
 *       )}
 *     </div>
 *   )
 * }
 * ```
 */
export function useUploadDataset(
  options?: Omit<
    UseMutationOptions<Dataset, Error, UploadDatasetRequest>,
    'mutationFn' | 'onSuccess'
  >
) {
  const queryClient = useQueryClient()

  return useMutation<Dataset, Error, UploadDatasetRequest>({
    mutationFn: (data: UploadDatasetRequest) => uploadDataset(data),
    onSuccess: (data) => {
      // Invalidate dataset list queries
      invalidateQueries(queryKeys.datasets.lists())

      // Invalidate specific dataset detail query
      invalidateQueries(queryKeys.datasets.detail(data.id))

      // If dataset is attached to an asset, invalidate asset queries
      if (data.asset) {
        invalidateQueries(queryKeys.assets.detail(data.asset))
        invalidateQueries(queryKeys.assets.lists())
      }

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, data as any, undefined as any)
    },
    ...options,
  })
}

