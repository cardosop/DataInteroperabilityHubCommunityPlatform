/**
 * useUserMutations Hook
 *
 * Mutation hooks for user management operations:
 * - Create user
 * - Update user
 * - Delete user
 * - Invite user
 * - Assign/remove roles
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query'
import {
  createUser,
  updateUser,
  deleteUser,
  inviteUser,
  assignUserRole,
  type CreateUserRequest,
  type UpdateUserRequest,
  type InviteUserRequest,
  type UserRoleAssignmentRequest,
  type User,
} from '@/lib/api/users'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useCreateUser Hook
 *
 * Mutation hook for creating a user.
 */
export function useCreateUser(
  options?: Omit<UseMutationOptions<User, Error, CreateUserRequest>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<User, Error, CreateUserRequest>({
    mutationFn: (data: CreateUserRequest) => createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

/**
 * useUpdateUser Hook
 *
 * Mutation hook for updating a user.
 */
export function useUpdateUser(
  options?: Omit<UseMutationOptions<User, Error, { id: string; data: UpdateUserRequest }>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<User, Error, { id: string; data: UpdateUserRequest }>({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() })
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(data.id) })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

/**
 * useDeleteUser Hook
 *
 * Mutation hook for deleting a user.
 */
export function useDeleteUser(
  options?: Omit<UseMutationOptions<void, Error, string>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<void, Error, string>({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

/**
 * useInviteUser Hook
 *
 * Mutation hook for inviting a user.
 */
export function useInviteUser(
  options?: Omit<UseMutationOptions<User, Error, InviteUserRequest>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<User, Error, InviteUserRequest>({
    mutationFn: (data: InviteUserRequest) => inviteUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

/**
 * useAssignUserRole Hook
 *
 * Mutation hook for assigning or removing a role from a user.
 */
export function useAssignUserRole(
  options?: Omit<UseMutationOptions<User, Error, { userId: string; data: UserRoleAssignmentRequest }>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<User, Error, { userId: string; data: UserRoleAssignmentRequest }>({
    mutationFn: ({ userId, data }) => assignUserRole(userId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() })
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(data.id) })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

