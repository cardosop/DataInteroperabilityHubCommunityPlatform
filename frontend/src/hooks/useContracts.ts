/**
 * useContracts Hook
 *
 * Query hook for listing contracts with filtering, sorting, and pagination.
 * Provides contract list functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function ContractsList() {
 *   const { data, isLoading, error } = useContracts({
 *     page: 1,
 *     page_size: 20,
 *     ordering: '-created_at',
 *     tag: ['analytics', 'sales']
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(contract => (
 *         <ContractCard key={contract.id} contract={contract} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import {
  listContracts,
  type ListContractsParams,
  type ListContractsResponse,
} from '@/lib/api/contracts'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useContracts Hook
 *
 * Query hook for listing contracts.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Contract list query result
 */
export function useContracts(
  params?: ListContractsParams,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<ListContractsResponse, Error>({
    queryKey: queryKeys.contracts.list(params),
    queryFn: async () => {
      return await listContracts(params)
    },
    enabled: options?.enabled !== false,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

