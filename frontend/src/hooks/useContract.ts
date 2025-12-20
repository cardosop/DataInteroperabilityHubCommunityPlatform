/**
 * useContract Hook
 *
 * Query hook for getting a single contract by ID.
 * Provides contract details with loading states and error handling.
 *
 * @example
 * ```tsx
 * function ContractDetail({ contractId }: { contractId: string }) {
 *   const { data: contract, isLoading, error } = useContract(contractId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *   if (!contract) return <NotFound />
 *
 *   return (
 *     <div>
 *       <h1>{contract.hub_contract_json.info?.name}</h1>
 *       <ContractViewer contract={contract} />
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import {
  getContract,
  type Contract,
} from '@/lib/api/contracts'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useContract Hook
 *
 * Query hook for getting a single contract by ID.
 *
 * @param id - Contract UUID
 * @param options - Additional React Query options
 * @returns Contract query result
 */
export function useContract(
  id: string,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<Contract, Error>({
    queryKey: queryKeys.contracts.detail(id),
    queryFn: async () => {
      return await getContract(id)
    },
    enabled: (options?.enabled !== false) && !!id,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

