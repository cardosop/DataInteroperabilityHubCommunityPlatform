/**
 * Phase 250.3.B.6 — frontend response interceptor for the
 * RFC-8594 ``Deprecation`` / ``Sunset`` headers emitted by
 * ``hub.apps.assets.middleware.AssetVisibilityDeprecationHeadersMiddleware``.
 *
 * The Asset visibility deprecation (D250.4) is the first user of
 * this interceptor, but the contract is generic — any backend
 * surface that emits the standard headers can opt in by mounting
 * its endpoint behind a middleware that sets:
 *
 *   Deprecation: true
 *   Sunset: <RFC-7231 date>
 *   Link: <doc-url>; rel="deprecation"
 *
 * **Behaviour:**
 *
 * * On the FIRST seen response carrying ``Deprecation: true`` for a
 *   given (path-prefix, sunset-date) pair, surface a one-time toast
 *   to admin users — no spam if the same endpoint is hit multiple
 *   times in the same session. Non-admin sessions see no toast (the
 *   deprecation is operator-targeted; end users have nothing to do).
 *
 * * The toast severity escalates as the sunset date approaches:
 *
 *   - ``> 30 days out``   → ``info`` (informational)
 *   - ``7 to 30 days out`` → ``warning``
 *   - ``< 7 days OR past`` → ``error`` (loud — phase-2 cutover imminent)
 *
 * * The deduplication key is ``${pathPrefix}:${sunsetDate}`` so a
 *   change in sunset date (e.g. operator extending the deprecation
 *   window) re-fires the toast on next call.
 *
 * **Design notes:**
 *
 * * Pure module — no React hooks. Callable from anywhere in the
 *   request pipeline. The toast surface is injected via
 *   ``configureDeprecationToast()`` so the interceptor can be
 *   unit-tested without a React tree.
 *
 * * No dependency on the API client's success / error path. This
 *   module reads response headers ONLY; it never reads or mutates
 *   the body. So a 4xx with a Deprecation header still triggers
 *   the toast — the response was deprecated regardless of whether
 *   the request succeeded.
 *
 * * Admin-detection is delegated via ``isAdminSession`` injection
 *   so the interceptor doesn't need to know about the auth shape
 *   used in this app (roles vs platform_admin vs scope strings).
 */

export interface DeprecationToast {
  warning: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

export interface DeprecationInterceptorConfig {
  /** The toast surface to emit notifications through. */
  toast: DeprecationToast;
  /** Predicate returning true iff the current session is an admin
   * (operator-targeted deprecations are silent for end users). */
  isAdminSession: () => boolean;
}

/** Module-level config — wired once at app startup. */
let _config: DeprecationInterceptorConfig | null = null;

/** Module-level dedup set — keyed by ``"${pathPrefix}:${sunset}"``. */
const _seenDeprecations = new Set<string>();

/**
 * Wire the interceptor with a toast surface + admin predicate.
 * Idempotent — calling more than once REPLACES the prior config.
 */
export function configureDeprecationInterceptor(
  config: DeprecationInterceptorConfig,
): void {
  _config = config;
}

/**
 * Reset the module-level dedup set + config. Used by tests.
 */
export function resetDeprecationInterceptor(): void {
  _config = null;
  _seenDeprecations.clear();
}

/**
 * Compute the path-prefix used for dedup. We strip query strings,
 * fragment IDs, and trailing IDs so ``/api/v1/assets/<uuid>/`` and
 * ``/api/v1/assets/?status=PUBLIC`` both dedup against the same
 * prefix ``/api/v1/assets``.
 */
function _normalisedPrefix(url: string): string {
  // Drop query + fragment.
  const [pathOnly] = url.split(/[?#]/);
  // Strip a trailing UUID-looking segment (8-4-4-4-12 hex), and any
  // numeric ID. Falls back to the path as-is if no ID match.
  return pathOnly
    .replace(
      /\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/?$/i,
      '/',
    )
    .replace(/\/\d+\/?$/, '/')
    .replace(/\/$/, '');
}

/**
 * Compute the toast severity from the parsed sunset date.
 */
function _severityFor(sunset: Date | null): 'info' | 'warning' | 'error' {
  if (sunset === null) {
    return 'warning';
  }
  const msUntil = sunset.getTime() - Date.now();
  const daysUntil = msUntil / (1000 * 60 * 60 * 24);
  if (daysUntil > 30) return 'info';
  if (daysUntil >= 7) return 'warning';
  return 'error';
}

/**
 * Best-effort RFC-7231 date parse. Returns null when the header
 * is absent / malformed (treat as "unknown sunset" — surface a
 * warning toast as the safe default).
 */
function _parseSunset(header: string | null | undefined): Date | null {
  if (!header) return null;
  const ms = Date.parse(header);
  if (Number.isNaN(ms)) return null;
  return new Date(ms);
}

/**
 * Format the toast body. Includes the relative time-to-sunset so
 * the operator can prioritise without clicking through to the doc.
 */
function _formatToastMessage(
  url: string,
  sunset: Date | null,
  link: string | null | undefined,
): string {
  const prefix = _normalisedPrefix(url) || url;
  let when = '';
  if (sunset !== null) {
    const days = Math.max(
      0,
      Math.round((sunset.getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
    );
    when = ` Sunset in ${days} day${days === 1 ? '' : 's'} (${sunset.toUTCString()}).`;
  }
  const docHint = link ? ` Migration guide: ${link}` : '';
  return `API endpoint ${prefix} is deprecated.${when}${docHint}`;
}

/**
 * Extract the document URL from the ``Link`` header's
 * ``rel="deprecation"`` entry. RFC-8288 syntax. Returns null when
 * absent or malformed.
 */
function _extractDeprecationLink(linkHeader: string | null | undefined): string | null {
  if (!linkHeader) return null;
  // RFC-8288 entries are comma-separated. Each entry looks like
  // ``<URL>; rel="deprecation"; type="text/markdown"``.
  for (const entry of linkHeader.split(',')) {
    const trimmed = entry.trim();
    if (!trimmed) continue;
    const relMatch = trimmed.match(/rel\s*=\s*"?deprecation"?/i);
    if (!relMatch) continue;
    const urlMatch = trimmed.match(/^<([^>]+)>/);
    if (urlMatch) return urlMatch[1];
  }
  return null;
}

/**
 * Inspect a fetch Response (or any object with a Headers-like
 * accessor) for the deprecation header trio and surface a one-time
 * admin toast when applicable. Safe to call on EVERY response —
 * non-deprecated responses are a single ``has("Deprecation")``
 * check + early return.
 *
 * The ``url`` argument should be the request path (used for the
 * dedup key + the toast body). Pass ``response.url`` if you have
 * it; otherwise the request path is fine.
 */
export function inspectResponseForDeprecation(
  url: string,
  headerGetter: (name: string) => string | null,
): void {
  if (_config === null) return;
  const deprecation = headerGetter('Deprecation');
  if (!deprecation || deprecation.toLowerCase() !== 'true') return;
  if (!_config.isAdminSession()) return;

  const sunsetHeader = headerGetter('Sunset');
  const sunset = _parseSunset(sunsetHeader);
  const dedupKey = `${_normalisedPrefix(url)}:${sunsetHeader ?? ''}`;
  if (_seenDeprecations.has(dedupKey)) return;
  _seenDeprecations.add(dedupKey);

  const linkHeader = headerGetter('Link');
  const docUrl = _extractDeprecationLink(linkHeader);
  const message = _formatToastMessage(url, sunset, docUrl);
  const severity = _severityFor(sunset);
  if (severity === 'error') {
    _config.toast.error(message);
  } else if (severity === 'warning') {
    _config.toast.warning(message);
  } else {
    _config.toast.info(message);
  }
}

/**
 * Convenience wrapper that takes a Headers-like object (from the
 * fetch Response) and forwards to ``inspectResponseForDeprecation``.
 * Internal API client code typically has the headers as a plain
 * ``Record<string, string>``; both shapes are accepted.
 */
export function inspectResponse(
  url: string,
  headers: Headers | Record<string, string>,
): void {
  const getter =
    headers instanceof Headers
      ? (name: string) => headers.get(name)
      : (name: string) =>
          headers[name] ??
          headers[name.toLowerCase()] ??
          // Defensive: HTTP headers are case-insensitive; some
          // proxies normalise to lowercase. Try the snake-case form
          // too in case the FE record uses ``deprecation``.
          null;
  inspectResponseForDeprecation(url, getter);
}
