/**
 * Wraps React Query's useMutation with default toast notifications.
 * Provides onSuccess toast and onError toast out of the box.
 * All default callbacks can be overridden per call-site.
 */
import { useMutation } from '@tanstack/react-query';
import type { UseMutationOptions, UseMutationResult } from '@tanstack/react-query';
import { useToast } from '../components/Toast';
import { isApiError } from '../types/api';
import { getErrorRemediation } from '../utils/errorUtils';

export interface MutationWithNotificationOptions<TData, TError, TVariables, TContext>
  extends UseMutationOptions<TData, TError, TVariables, TContext> {
  /** Message shown on success (or function producing it). Default: none (silent). */
  successMessage?: string | ((data: TData, variables: TVariables) => string);
  /** Message shown on error. Default: extracted from error or 'An error occurred'. */
  errorMessage?: string | ((error: TError) => string);
}

function getErrorMessage(error: unknown): string {
  // Phase 227 Wave 1 (227.L5.9) — when the error carries a known typed
  // code (STRUCTURELESS_CONTRACT, PRECONDITION_FAILED, SCHEMA_TOO_DEEP,
  // …), surface the user-friendly remediation copy from
  // ``getErrorRemediation`` instead of the raw API message. This keeps
  // toast notifications across contract create / edit / publish in
  // sync with the Schema-editor's inline-banner remediation text.
  if (isApiError(error)) {
    const code = error.error.code;
    const subcode =
      typeof error.error.details?.subcode === 'string' ? error.error.details.subcode : undefined;
    const remediationDetails =
      typeof error.error.details?.remediation_url === 'string'
        ? { remediation_url: error.error.details.remediation_url }
        : undefined;
    const remediation = getErrorRemediation(code, subcode, remediationDetails);
    if (remediation) {
      return remediation.title;
    }
    const detailMessage =
      typeof error.error.details?.error === 'string' ? error.error.details.error : null;
    return detailMessage || error.error.message || 'An unexpected error occurred';
  }
  // Some axios-shaped errors carry a top-level ``code`` + nested
  // ``response.data`` — handle that path before falling back to raw msg.
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error
  ) {
    const resp = (error as {
      response?: {
        data?: {
          code?: string;
          detail?: string;
          message?: string;
          details?: { subcode?: string; remediation_url?: string };
        };
      };
    }).response;
    const code = resp?.data?.code;
    const subcode = resp?.data?.details?.subcode;
    const remediationDetails =
      typeof resp?.data?.details?.remediation_url === 'string'
        ? { remediation_url: resp.data.details.remediation_url }
        : undefined;
    if (code) {
      const remediation = getErrorRemediation(code, subcode, remediationDetails);
      if (remediation) return remediation.title;
    }
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
