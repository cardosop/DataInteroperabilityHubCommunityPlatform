/**
 * Extracts blocker list from an activation error.
 * Handles the normalized ApiError shape from the client interceptor:
 *   { error: { code: 'ASSET_ACTIVATION_BLOCKED', details: string[] | Record<string, unknown> } }
 * Also handles the raw axios error shape for resilience.
 *
 * Lives in its own module (rather than co-located with
 * ``ActivationBlockerDialog``) so Vite's Fast Refresh boundary stays
 * component-only. ``react-refresh/only-export-components`` enforces
 * this — without the split, edits to the dialog component invalidate
 * the helper too and HMR falls back to a full page reload.
 */
export function extractBlockersFromError(err: unknown): string[] | null {
  if (!err || typeof err !== 'object') return null;

  // Normalized ApiError shape: { error: { code, details } }
  const apiErr = err as {
    error?: { code?: string; details?: unknown; message?: string };
    response?: { data?: { code?: string; details?: unknown; error?: string } };
  };

  // Extract the error payload from either the normalized shape or raw axios
  const payload =
    apiErr.error ?? apiErr.response?.data ?? null;

  if (!payload || typeof payload !== 'object') return null;

  const data = payload as {
    code?: string;
    details?: unknown;
    error?: string;
    message?: string;
  };

  // Recognise the full set of blocker codes the activate endpoint returns
  // (Phase 274.2.2 three-state taxonomy).  Previously only
  // `ASSET_ACTIVATION_BLOCKED` was matched; any other code (including
  // `COMPLIANCE_SCAN_PENDING`, `COMPLIANCE_SCAN_FAILED`,
  // `COMPLIANCE_NOT_ALLOWED_TO_STORE`, `COMPLIANCE_THRESHOLD_EXCEEDED`,
  // and the generic blocker_code fallback) silently returned null,
  // suppressing the ActivationBlockerDialog.
  const isActivationError =
    data.code === 'ASSET_ACTIVATION_BLOCKED' ||
    data.code === 'COMPLIANCE_SCAN_PENDING' ||
    data.code === 'COMPLIANCE_SCAN_FAILED' ||
    data.code === 'COMPLIANCE_NOT_ALLOWED_TO_STORE' ||
    data.code === 'COMPLIANCE_THRESHOLD_EXCEEDED' ||
    // Catch-all: any error whose message indicates activation was blocked
    (typeof data.error === 'string' && /cannot activate|activation.*blocked|requirements.*not met/i.test(data.error)) ||
    (typeof data.message === 'string' && /cannot activate|activation.*blocked|requirements.*not met/i.test(data.message));

  if (!isActivationError) return null;

  const details = data.details;
  if (Array.isArray(details)) return details as string[];
  if (details && typeof details === 'object') {
    return Object.values(details).flat().map(String);
  }
  // Last resort: return the code or the error message itself
  const fallback = data.error ?? data.code ?? 'Activation blocked';
  return [String(fallback)];
}
