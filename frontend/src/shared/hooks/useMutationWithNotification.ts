/**
 * Wraps React Query's useMutation with default toast notifications.
 * Provides onSuccess toast and onError toast out of the box.
 * All default callbacks can be overridden per call-site.
 */
import { useMutation } from '@tanstack/react-query';
import type { UseMutationOptions, UseMutationResult } from '@tanstack/react-query';
import { useToast } from '../components/Toast';
import { isApiError } from '../types/api';

export interface MutationWithNotificationOptions<TData, TError, TVariables, TContext>
  extends UseMutationOptions<TData, TError, TVariables, TContext> {
  /** Message shown on success (or function producing it). Default: none (silent). */
  successMessage?: string | ((data: TData, variables: TVariables) => string);
  /** Message shown on error. Default: extracted from error or 'An error occurred'. */
  errorMessage?: string | ((error: TError) => string);
}

function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    const detailMessage =
      typeof error.error.details?.error === 'string' ? error.error.details.error : null;
    return detailMessage || error.error.message || 'An unexpected error occurred';
  }
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error
  ) {
    const resp = (error as { response?: { data?: { detail?: string; message?: string } } }).response;
    if (resp?.data?.detail) return resp.data.detail;
    if (resp?.data?.message) return resp.data.message;
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred';
}

export function useMutationWithNotification<
  TData = unknown,
  TError = unknown,
  TVariables = void,
  TContext = unknown,
>(
  options: MutationWithNotificationOptions<TData, TError, TVariables, TContext>
): UseMutationResult<TData, TError, TVariables, TContext> {
  const toast = useToast();
  const { successMessage, errorMessage, onSuccess, onError, ...rest } = options;

  return useMutation({
    ...rest,
    onSuccess: (data, variables, context) => {
      if (successMessage) {
        const msg =
          typeof successMessage === 'function'
            ? successMessage(data, variables)
            : successMessage;
        toast.success(msg);
      }
      onSuccess?.(data, variables, context);
    },
    onError: (error, variables, context) => {
      const msg =
        typeof errorMessage === 'function'
          ? errorMessage(error)
          : errorMessage ?? getErrorMessage(error);
      if (msg) {
        toast.error(msg);
      }
      onError?.(error, variables, context);
    },
  });
}
