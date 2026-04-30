/**
 * Error Utilities
 * Functions for normalizing and handling errors consistently across the application
 */

import type { ApiError } from '../types/api';

/* -------------------------------------------------------------------------
 * Phase 227 Wave 1 (227.L5.9) — Known error codes + remediation copy
 * ------------------------------------------------------------------------- */

/**
 * Backend error codes the frontend specifically recognises.
 *
 * Add a new entry here when the backend introduces a typed
 * ``ValidationError(code=...)`` that has bespoke remediation copy.
 * Anything not in this enum falls through to a generic
 * "An unexpected error occurred" message.
 */
export const KnownErrorCode = {
  /** Phase 227 L3 — structureless contract on create / update / publish. */
  STRUCTURELESS_CONTRACT: 'STRUCTURELESS_CONTRACT',
  /** Phase 227 L4.3 — ETag/If-Match mismatch on PATCH. */
  PRECONDITION_FAILED: 'PRECONDITION_FAILED',
  /** Phase 227 L2.1 — schema nesting depth exceeded. */
  SCHEMA_TOO_DEEP: 'SCHEMA_TOO_DEEP',
  /** Generic Pydantic-level validation failure. */
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  /** Backend reachable but normalization itself failed. */
  NORMALIZATION_FAILED: 'NORMALIZATION_FAILED',
  /** Tenant lacks required role. */
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  /** Tenant exceeded a quota / plan limit. */
  PLAN_LIMIT_EXCEEDED: 'PLAN_LIMIT_EXCEEDED',
} as const;
export type KnownErrorCode = (typeof KnownErrorCode)[keyof typeof KnownErrorCode];

/** Remediation hint shown to the user; some include a deep-link. */
export interface ErrorRemediation {
  /** Short one-line summary suitable for a toast. */
  title: string;
  /** Multi-line guidance suitable for an inline banner. */
  details: string;
  /** Optional deep-link the UI should expose as a "Fix this" CTA. */
  ctaUrl?: string;
  /** Optional CTA label paired with ``ctaUrl``. */
  ctaLabel?: string;
}

const STRUCTURELESS_SUBCODE_HINTS: Record<string, string> = {
  STRUCTURELESS_ODPS_NO_PORTS:
    'ODPS contract has no resolvable outputPort schemas. Add at least one outputPort with a `contract.spec.schema.fields[]`, `dataSchema.fields[]`, or a `contractId` referencing an existing ODCS contract.',
  STRUCTURELESS_ODCS_NO_SCHEMA:
    'ODCS contract has no `schema.fields[]` and no `models[*].fields[]`. Open the Schema editor to add at least one model with one field.',
  STRUCTURELESS_CYCLIC_PORTS:
    'ODPS port resolution detected a cycle (A → B → A). Fix the circular contractId reference, then retry.',
  STRUCTURELESS_GENERIC:
    'Contract has no resolvable structure. Add models or schema fields and retry.',
};

/**
 * Build a UI-friendly remediation envelope from a backend error code +
 * optional subcode. Returns ``null`` when the code is not a
 * known one — callers should fall back to the raw API message.
 *
 * Phase 227 L5.9 — applied across contract create / edit toast
 * notifications and the Schema-editor inline banner.
 */
export function getErrorRemediation(
  code: string | null | undefined,
  subcode?: string | null,
  details?: { remediation_url?: string | null } | null,
): ErrorRemediation | null {
  if (!code) return null;
  const normalisedCode = String(code).toUpperCase();

  switch (normalisedCode) {
    case KnownErrorCode.STRUCTURELESS_CONTRACT: {
      const subcodeKey = (subcode ?? '').toUpperCase();
      const detail =
        STRUCTURELESS_SUBCODE_HINTS[subcodeKey] ?? STRUCTURELESS_SUBCODE_HINTS.STRUCTURELESS_GENERIC;
      const ctaUrl = details?.remediation_url ?? undefined;
      return {
        title: 'Contract has no models or schema fields',
        details: detail,
        ctaUrl,
        ctaLabel: ctaUrl ? 'Open Schema editor' : undefined,
      };
    }
    case KnownErrorCode.PRECONDITION_FAILED:
      return {
        title: 'Contract changed since you opened it',
        details:
          'Someone else updated this contract while you were editing. Refresh to see their changes (you may need to re-apply yours), or open the contract in a new tab to compare.',
        ctaLabel: 'Refresh',
      };
    case KnownErrorCode.SCHEMA_TOO_DEEP:
      return {
        title: 'Schema nesting too deep',
        details:
          'The contract exceeds the maximum nesting depth (default 20). Flatten deeply-nested objects/arrays or split into multiple models.',
      };
    case KnownErrorCode.VALIDATION_ERROR:
      return {
        title: 'Contract validation failed',
        details:
          'One or more fields are invalid. Check the highlighted rows and fix the listed issues before saving.',
      };
    case KnownErrorCode.NORMALIZATION_FAILED:
      return {
        title: 'Could not parse contract',
        details:
          'The backend rejected the contract. Check the raw payload for missing required fields or malformed JSON/YAML.',
      };
    case KnownErrorCode.PERMISSION_DENIED:
      return {
        title: "You don't have permission for this action",
        details:
          'Your current role cannot perform this operation. Ask a TENANT_ADMIN to grant the required role or perform the action on your behalf.',
      };
    case KnownErrorCode.PLAN_LIMIT_EXCEEDED:
      return {
        title: 'Plan limit reached',
        details:
          'Your tenant has reached its plan quota for this resource. Upgrade your plan or remove unused resources before retrying.',
      };
    default:
      return null;
  }
}

/**
 * Normalizes various error inputs into a consistent ApiError shape
 *
 * @param err - Error input (Error instance, string, ApiError from client, or unknown)
 * @returns Normalized ApiError with all required fields
 */
export function normalizeError(err: unknown): ApiError {
  // Already an ApiError (from apiClient)
  if (err && typeof err === 'object' && 'error' in err) {
    const apiError = err as ApiError;
    // Ensure all required fields are present
    return {
      error: {
        code: apiError.error.code || 'UNKNOWN_ERROR',
        message: apiError.error.message || 'An error occurred',
        http_status: apiError.error.http_status || 500,
        request_id: apiError.error.request_id || 'unknown',
        timestamp: apiError.error.timestamp || new Date().toISOString(),
        details: apiError.error.details,
        field_errors: apiError.error.field_errors,
      },
    };
  }

  // JavaScript Error instance
  if (err instanceof Error) {
    return {
      error: {
        code: 'JAVASCRIPT_ERROR',
        message: err.message || 'An unexpected error occurred',
        http_status: 500,
        request_id: 'unknown',
        timestamp: new Date().toISOString(),
        details: {
          name: err.name,
          stack: err.stack,
        },
      },
    };
  }

  // String error
  if (typeof err === 'string') {
    return {
      error: {
        code: 'STRING_ERROR',
        message: err || 'An error occurred',
        http_status: 500,
        request_id: 'unknown',
        timestamp: new Date().toISOString(),
      },
    };
  }

  // Unknown error type
  return {
    error: {
      code: 'UNKNOWN_ERROR',
      message: 'An unexpected error occurred',
      http_status: 500,
      request_id: 'unknown',
      timestamp: new Date().toISOString(),
      details: {
        original: String(err),
      },
    },
  };
}
