/**
 * useRegister Hook
 *
 * Mutation hook for user registration.
 * Provides registration functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function RegisterForm() {
 *   const register = useRegister()
 *
 *   const handleSubmit = async (e: FormEvent) => {
 *     e.preventDefault()
 *     try {
 *       await register.mutateAsync({
 *         email: 'user@example.com',
 *         password: 'SecurePass123',
 *         name: 'John Doe'
 *       })
 *       // Show success message and redirect to login
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <!-- form fields -->
 *       <button disabled={register.isPending}>Register</button>
 *     </form>
 *   )
 * }
 * ```
 */

import { useMutation } from '@tanstack/react-query'
import {
  register as apiRegister,
  type RegisterRequest,
  type RegisterResponse,
} from '@/lib/api/auth'

/**
 * useRegister Hook
 *
 * Mutation hook for user registration.
 *
 * Note: Registration does not automatically log in the user.
 * The user must login separately after successful registration.
 *
 * @returns Register mutation object with mutate, mutateAsync, and state
 */
export function useRegister() {
  return useMutation<RegisterResponse, Error, RegisterRequest>({
    mutationFn: async (data) => {
      return await apiRegister(data)
    },
    onError: (error) => {
      // Error handling is done by the caller
      console.error('[Register] Registration failed:', error)
    },
    onSuccess: () => {
      // Success handling can be done by the caller
      // Typically, you would show a success message and redirect to login
    },
  })
}

