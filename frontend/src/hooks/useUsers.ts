/**
 * useUsers Hook
 *
 * Query hook for listing users with filtering, sorting, and pagination.
 * Provides user list functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function UsersList() {
 *   const { data, isLoading, error } = useUsers({
 *     page: 1,
 *     page_size: 20,
 *     ordering: '-created_at',
 *     status: 'ACTIVE'
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(user => (
 *         <UserCard key={user.id} user={user} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { listUsers, type ListUsersParams, type ListUsersResponse } from '@/lib/api/users'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useUsers Hook
 *
 * Query hook for listing users.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Users list query result
 */
export function useUsers(
  params?: ListUsersParams,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<ListUsersResponse, Error>({
    queryKey: queryKeys.users.list(params),
    queryFn: async () => {
      return await listUsers(params)
    },
    enabled: options?.enabled !== false,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

