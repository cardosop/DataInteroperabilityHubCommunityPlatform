/**
 * useOptimisticMutation — canonical optimistic UI for low-risk mutations (278.F.3).
 *
 * Wraps React Query's ``useMutation`` with automatic:
 *   1. ``onMutate``: snapshots affected query cache entries, applies
 *      the optimistic update, cancels in-flight refetches.
 *   2. ``onError``: rolls back cache to snapshot, fires toast with error.
 *   3. ``onSettled``: invalidates affected queries to re-fetch truth.
 *
 * Use for low-risk mutations: favorite toggle, tag add/remove, status
 * hover-update, preference toggle. Do NOT use for destructive actions,
 * monetary transactions, or multi-step workflows.
 */
import {
  type QueryKey,
  useMutation,
  type UseMutationOptions,
  type UseMutationResult,
  useQueryClient,
} from '@tanstack/react-query';
import { useToast } from '../../shared/components/Toast/useToast';

export interface OptimisticMutationOptions<
  TData = unknown,
  TError = Error,
  TVariables = void,
  TContext = unknown,
> extends UseMutationOptions<TData, TError, TVariables, TContext> {
  /** Query keys to invalidate on settle. */
  invalidateKeys?: QueryKey[];
  /**
   * Apply the optimistic update to the cache. Return a rollback snapshot.
   * Called inside ``onMutate`` after cancelling in-flight queries.
   */
  optimisticUpdate?: (variables: TVariables) => TContext;
  /** Rollback snapshot. Called inside ``onError`` to undo optimistic update. */
  rollback?: (context: TContext) => void;
  /** Success toast message. */
  successMessage?: string;
  /** Error toast message. */
  errorMessage?: string;
}

export function useOptimisticMutation<
  TData = unknown,
  TError = Error,
  TVariables = void,
  TContext = unknown,
>(
  options: OptimisticMutationOptions<TData, TError, TVariables, TContext>,
): UseMutationResult<TData, TError, TVariables> {
  const queryClient = useQueryClient();
  const toast = useToast();
  const {
    invalidateKeys,
    optimisticUpdate,
    rollback,
    successMessage,
    errorMessage,
    onSuccess,
    onError,
    onSettled,
    onMutate,
    ...rest
  } = options;

  return useMutation<TData, TError, TVariables, TContext>({
    ...rest,
    onMutate: async (variables) => {
      // Cancel in-flight queries so they don't overwrite optimistic state
      if (invalidateKeys) {
        await Promise.all(
          invalidateKeys.map((key) => queryClient.cancelQueries({ queryKey: key })),
        );
      }
      const userContext = await onMutate?.(variables);
      const optContext = optimisticUpdate?.(variables);
      return (optContext ?? userContext) as TContext;
    },
    onError: (err, variables, context) => {
      if (rollback) rollback(context as TContext);
      if (errorMessage) toast.error(errorMessage);
      onError?.(err, variables, context);
    },
    onSuccess: (data, variables, context) => {
      if (successMessage) toast.success(successMessage);
      onSuccess?.(data, variables, context);
    },
    onSettled: (data, error, variables, context) => {
      if (invalidateKeys) {
        invalidateKeys.forEach((key) =>
          queryClient.invalidateQueries({ queryKey: key }),
        );
      }
      onSettled?.(data, error, variables, context);
    },
  });
}
