/**
 * Plain-language error translations for all backend error codes (278.D.3).
 *
 * Single source of truth mapping every known backend error code to
 * a humane, actionable message.  Read alongside
 * ``docs/api/error-codes.md`` and ``docs/api/business-rule-error-codes.md``.
 */
export interface ErrorTranslation {
  /** Short, toast-suitable title. */
  title: string;
  /** Longer inline-banner description, may include HTML. */
  description: string;
  /** Optional deep-link to a settings page, docs, or remediation flow. */
  actionUrl?: string;
  /** Label for the action button/link. */
  actionLabel?: string;
}

const ERROR_TRANSLATIONS: Record<string, ErrorTranslation> = {
  // ── Asset errors ───────────────────────────────────────────────────────
  ASSET_NOT_FOUND: {
    title: 'Asset not found',
    description: 'This asset may have been deleted, archived, or you may not have access to it.',
  },
  ASSET_FAIL_CLOSED_REJECTED: {
    title: 'Asset blocked by fail-closed policy',
    description: 'Your tenant has fail-closed mode enabled. The asset cannot be created until the required validations pass.',
    actionUrl: '/settings/tenant',
    actionLabel: 'Review tenant settings',
  },
  ASSET_VERSION_MISMATCH: {
    title: 'Asset was modified by another session',
    description: 'Someone else updated this asset while you were editing. Refresh to see the latest version.',
    actionLabel: 'Refresh',
  },
  ASSET_CREATION_DISABLED: {
    title: 'Asset creation is disabled',
    description: 'Your tenant plan does not allow creating new assets. Upgrade your plan to enable this feature.',
    actionUrl: '/settings/billing',
    actionLabel: 'Upgrade plan',
  },

  // ── File errors ────────────────────────────────────────────────────────
  FILE_TOO_LARGE_FOR_INFERENCE: {
    title: 'File too large',
    description: 'This file exceeds the maximum size for ML inference. Try splitting it into smaller files.',
  },
  UNSUPPORTED_FILE_FORMAT: {
    title: 'Unsupported file format',
    description: 'This file type is not supported. Accepted formats include CSV, JSON, Parquet, and Avro.',
  },
  FILE_DOWNLOAD_CHECKSUM_MISMATCH: {
    title: 'Download verification failed',
    description: 'The downloaded file does not match the expected checksum. The file may have been corrupted during transfer.',
    actionLabel: 'Retry download',
  },
  FILE_IDOR_ATTEMPT_BLOCKED: {
    title: 'Access denied',
    description: 'You do not have permission to access this file.',
  },

  // ── Marketplace errors ─────────────────────────────────────────────────
  PLAN_LIMIT_EXCEEDED: {
    title: 'Plan limit reached',
    description: 'You have reached the limit for your current plan. Upgrade to increase your limits.',
    actionUrl: '/settings/billing',
    actionLabel: 'Upgrade plan',
  },

  // ── Compliance errors ──────────────────────────────────────────────────
  COMPLIANCE_DEGRADED_BLOCKED: {
    title: 'Compliance scan unavailable',
    description: 'The compliance service is currently degraded. Your request will be processed when the service recovers.',
  },
  COMPLIANCE_RUN_REQUIRED: {
    title: 'Compliance check required',
    description: 'A successful compliance scan is required before you can proceed. Run a scan and try again.',
    actionLabel: 'Run compliance scan',
  },
  COMPLIANCE_THRESHOLD_EXCEEDED: {
    title: 'Compliance threshold exceeded',
    description: 'The asset risk level exceeds your tenant compliance threshold. Review the detected issues or adjust your threshold.',
    actionUrl: '/settings/tenant',
    actionLabel: 'Review threshold',
  },
  COMPLIANCE_FORCE_PUBLISH_DENIED: {
    title: 'Force publish denied',
    description: 'Only platform administrators can bypass compliance gates.',
  },

  // ── Governance / ABAC errors ───────────────────────────────────────────
  ABAC_POLICY_DENIED: {
    title: 'Policy denied',
    description: 'Your request was denied by an access control policy. Contact your tenant administrator if you believe this is an error.',
  },
  PERMISSION_DENIED: {
    title: 'Permission denied',
    description: 'You do not have the required permissions to perform this action. Contact your tenant administrator.',
  },

  // ── Validation errors ──────────────────────────────────────────────────
  VALIDATION_ERROR: {
    title: 'Validation failed',
    description: 'Some fields contain invalid values. Check the highlighted fields and try again.',
  },
  STRUCTURELESS_CONTRACT: {
    title: 'Contract structure required',
    description: 'This contract needs a defined schema before it can be used. Open the Schema editor to define the structure.',
    actionUrl: '/contracts',
    actionLabel: 'Open Schema editor',
  },
  CONTRACT_STRUCTURELESS_REJECTED: {
    title: 'Structureless contract rejected',
    description: 'Your tenant requires structured contracts. Add a schema definition before publishing.',
    actionUrl: '/contracts',
    actionLabel: 'Define schema',
  },
  SCHEMA_TOO_DEEP: {
    title: 'Schema too complex',
    description: 'The schema nesting depth exceeds the maximum allowed. Simplify the structure and try again.',
  },
  NORMALIZATION_FAILED: {
    title: 'Contract normalization failed',
    description: 'The contract could not be parsed. Check the format and structure, then try again.',
  },
  PRECONDITION_FAILED: {
    title: 'Concurrent edit detected',
    description: 'This resource was modified while you were editing. Your changes have been saved — review the latest version.',
    actionLabel: 'Refresh',
  },

  // ── Idempotency errors ─────────────────────────────────────────────────
  IDEMPOTENCY_KEY_BODY_MISMATCH: {
    title: 'Request mismatch',
    description: 'The request body does not match the idempotency key. This usually means the retry attempt differs from the original request.',
  },
  IDEMPOTENCY_KEY_REQUIRED: {
    title: 'Idempotency key required',
    description: 'This endpoint requires an Idempotency-Key header for safe retries.',
  },

  // ── Rate limiting ─────────────────────────────────────────────────────
  RATE_LIMIT_EXCEEDED: {
    title: 'Rate limit reached',
    description: 'Too many requests. Please wait a moment and try again.',
  },

  // ── Workflow errors ───────────────────────────────────────────────────
  WORKFLOW_RUN_NOT_FOUND: {
    title: 'Workflow run not found',
    description: 'This workflow execution may have been deleted or archived.',
  },
  WORKFLOW_VERSION_MIGRATION_REQUIRED: {
    title: 'Workflow version outdated',
    description: 'This workflow definition needs to be migrated to the latest version.',
  },

  // ── Connectivity / infrastructure ──────────────────────────────────────
  CROSS_SERVICE_VERSION_MISMATCH: {
    title: 'Service version mismatch',
    description: 'A backend service is running an incompatible version. The team has been notified.',
  },
  COMPLIANCE_SERVICE_UNAVAILABLE: {
    title: 'Compliance service unavailable',
    description: 'The compliance service is temporarily unreachable. Your request will be queued.',
  },

  // ── Generic / client-side ──────────────────────────────────────────────
  JAVASCRIPT_ERROR: {
    title: 'Something went wrong',
    description: 'An unexpected error occurred. Please try again or contact support if the issue persists.',
  },
  NETWORK_ERROR: {
    title: 'Network error',
    description: 'Could not reach the server. Check your internet connection and try again.',
    actionLabel: 'Retry',
  },
  UNKNOWN_ERROR: {
    title: 'Unexpected error',
    description: 'An unexpected error occurred. Please try again or contact support.',
  },
  STRING_ERROR: {
    title: 'Error',
    description: 'An error occurred. Please try again.',
  },

  // ── Tenant/Plan errors ─────────────────────────────────────────────────
  PLAN_NOT_FOUND: {
    title: 'Plan not found',
    description: 'Your tenant does not have an active plan. Contact support to resolve this.',
  },
  TENANT_NOT_FOUND: {
    title: 'Tenant not found',
    description: 'Your organization could not be found. Contact support if this persists.',
  },
};

/**
 * Look up a humane translation for a backend error code.
 * Falls back to a generic message for unknown codes.
 */
export function translateError(code: string | null | undefined): ErrorTranslation {
  if (!code) return ERROR_TRANSLATIONS.UNKNOWN_ERROR;
  const entry = ERROR_TRANSLATIONS[code];
  if (entry) return entry;

  // Heuristic: try to derive meaning from code pattern
  if (code.endsWith('_NOT_FOUND')) {
    return {
      title: 'Resource not found',
      description: `The requested ${code.replace('_NOT_FOUND', '').toLowerCase().replace(/_/g, ' ')} could not be found.`,
    };
  }
  if (code.endsWith('_DENIED') || code.endsWith('_BLOCKED')) {
    return {
      title: 'Access denied',
      description: 'You do not have permission to perform this action.',
    };
  }

  return ERROR_TRANSLATIONS.UNKNOWN_ERROR;
}

export const ALL_ERROR_TRANSLATIONS = ERROR_TRANSLATIONS;
