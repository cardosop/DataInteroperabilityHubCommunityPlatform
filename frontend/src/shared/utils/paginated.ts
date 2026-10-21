/**
 * Paginated-response normalization (Phase 1.5 follow-up).
 *
 * Every backend list endpoint is paginated via the DRF global
 * ``StandardPageNumberPagination`` (``hub/settings.py:1692``), so list
 * responses carry the envelope ``{count, ..., results: [...]}``. Frontend
 * components historically guarded only the ENVELOPE (``!data || ...``) and
 * then called ``data.results.map/.find/.length`` — a 200 whose body is a
 * non-envelope object (proxy error envelope, schema drift) left ``results``
 * undefined and crashed the render (the ``tenants.find`` class).
 *
 * Hooks and services normalize ``results`` through these helpers AT THE
 * BOUNDARY so every consumer sees an array, always. Component-level
 * ``!data || data.results.length === 0`` guards remain valid: with ``[]``
 * they read 0 and render the empty state, exactly as before.
 */

/** Unwrap ``payload.results`` if it is an array, else ``[]``. */
export function unwrapResults<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) {
    return payload as T[];
  }
  const results = (payload as { results?: unknown } | null | undefined)?.results;
  return Array.isArray(results) ? (results as T[]) : [];
}

/** Normalize a paginated envelope so ``results`` is always an array. */
export function normalizePaginated<T extends object>(
  payload: T | null | undefined
): T & { results: unknown[] } {
  const envelope = (payload ?? {}) as T & { results: unknown };
  return {
    ...envelope,
    results: Array.isArray(envelope.results) ? envelope.results : [],
  };
}
