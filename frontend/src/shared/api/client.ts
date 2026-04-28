/**
 * API Client — Phase 209: native fetch replacement for axios
 *
 * Uses browser-native fetch() wrapped in a compatibility layer that returns
 * { data: T, status, headers } — matching the AxiosResponse<T> shape so all
 * 38+ service files calling `response.data` need zero changes.
 *
 * Supply chain context: axios npm maintainer account was compromised (DPRK-linked
 * UNC1069/WAVESHAPER published axios@1.14.1 with RAT). This client eliminates
 * the axios dependency entirely — zero npm packages for HTTP.
 */

import { errorReportingService } from '../services/errorReporting';
import { performanceMetricsService } from '../services/performanceMetrics';
import type { ApiError, ApiResponse, HttpClient, RequestConfig } from '../types/api';

/** Raw API error response — backend may return nested { error: {...} } or flat { error, code, ... } */
type RawErrorResponse = ApiError | Record<string, unknown>;

/** Extract first error message from DRF serializer validation format: { "field": ["message"] } */
function extractFirstDrfFieldError(obj: Record<string, unknown>): string | undefined {
  for (const v of Object.values(obj)) {
    if (Array.isArray(v) && v.length > 0) {
      const first = v[0];
      if (typeof first === 'string') return first;
    }
    if (typeof v === 'string') return v;
  }
  return undefined;
}

/** Read CSRF token from Django's csrftoken cookie */
function readCsrfToken(): string | undefined {
  if (typeof document === 'undefined') return undefined;
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1];
}

// Use relative URL in browser to leverage Vite proxy, or full URL if explicitly set
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** Parse response body based on responseType config */
async function parseResponseBody<T>(response: Response, responseType?: string): Promise<T> {
  if (responseType === 'blob') {
    return (await response.blob()) as T;
  }
  if (responseType === 'text') {
    return (await response.text()) as T;
  }
  // Default: JSON. Handle empty responses (204 No Content)
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

/** Convert Headers to plain Record for ApiResponse compatibility */
function headersToRecord(headers: Headers): Record<string, string> {
  const result: Record<string, string> = {};
  headers.forEach((value, key) => {
    result[key] = value;
  });
  return result;
}

/**
 * Normalize backend error response to ApiError shape.
 * Handles both nested { error: { code, message } } and flat DRF { detail } formats.
 */
function normalizeApiError(
  responseData: RawErrorResponse | null,
  httpStatus: number,
  correlationId: string,
): ApiError['error'] {
  const errObj = responseData?.error;
  const hasNested =
    errObj && typeof errObj === 'object' && !Array.isArray(errObj) && 'code' in errObj;

  if (hasNested) {
    const e = errObj as ApiError['error'];
    return {
      code: e.code || 'UNKNOWN_ERROR',
      message: e.message || 'An error occurred',
      http_status: httpStatus,
      request_id: correlationId || e.request_id || 'unknown',
      timestamp: e.timestamp || new Date().toISOString(),
      details: e.details,
      field_errors: e.field_errors,
    };
  }

  if (responseData && typeof responseData === 'object') {
    const r = responseData as Record<string, unknown>;
    const detailMsg = typeof r.detail === 'string' ? r.detail : undefined;
    const errorMsg = typeof r.error === 'string' ? r.error : undefined;
    const drfFieldMsg = extractFirstDrfFieldError(r);
    return {
      code: (r.code as string) || 'UNKNOWN_ERROR',
      message: detailMsg ?? errorMsg ?? drfFieldMsg ?? 'An error occurred',
      http_status: httpStatus,
      request_id: correlationId || 'unknown',
      timestamp: (r.timestamp as string) || new Date().toISOString(),
      // Preserve full response body in details so callers can access non-standard
      // fields (e.g., 402 Payment Required returns requires_action, client_secret
      // at the top level which don't fit the nested ApiError shape).
      details:
        (r.details as Record<string, unknown>) ||
        (typeof r.error === 'object' && r.error !== null && !Array.isArray(r.error)
          ? (r.error as Record<string, unknown>)
          : r as Record<string, unknown>),
      field_errors: r.field_errors as ApiError['error']['field_errors'],
    };
  }

  // Fall back to HTTP status-based error code so that 404/403/500 responses
  // with non-JSON bodies (e.g. HTML from reverse proxy) still produce a
  // meaningful code instead of the opaque UNKNOWN_ERROR.
  const HTTP_STATUS_CODE_MAP: Record<number, string> = {
    400: 'VALIDATION_ERROR',
    401: 'AUTH_UNAUTHORIZED',
    403: 'AUTH_FORBIDDEN',
    404: 'NOT_FOUND',
    409: 'CONFLICT_ERROR',
    429: 'RATE_LIMIT_EXCEEDED',
    500: 'INTERNAL_ERROR',
    502: 'SERVICE_UNAVAILABLE',
    503: 'SERVICE_UNAVAILABLE',
    504: 'SERVICE_UNAVAILABLE',
  };

  const HTTP_STATUS_MESSAGE_MAP: Record<number, string> = {
    400: 'Bad request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'The requested resource was not found',
    409: 'Resource conflict',
    429: 'Too many requests',
    500: 'Internal server error',
    502: 'Service temporarily unavailable',
    503: 'Service temporarily unavailable',
    504: 'Request timed out (gateway)',
  };

  return {
    code: HTTP_STATUS_CODE_MAP[httpStatus] || 'UNKNOWN_ERROR',
    message: HTTP_STATUS_MESSAGE_MAP[httpStatus] || 'An error occurred',
    http_status: httpStatus,
    request_id: correlationId || 'unknown',
    timestamp: new Date().toISOString(),
    details: responseData ? { raw: responseData } : undefined,
  };
}

/**
 * Endpoints that must be reached WITHOUT an `Authorization: Bearer` header,
 * even when the client happens to have a token in memory from a prior
 * session.
 *
 * Why this exists: the backend's auth middleware validates the Authorization
 * header BEFORE reading the request body. If a stale/revoked/invalid bearer
 * is attached to `/auth/login/`, the backend returns 401 without ever
 * looking at the email+password in the body — the login request fails even
 * though the credentials are valid. The user then retries, localStorage
 * gets cleared on the 401, and the second attempt succeeds (no stale
 * header). This produces the classic "first login always fails, second
 * works" UX regression.
 *
 * These endpoints are anonymous by definition — a user hits them BEFORE
 * having a session — so the Authorization header is never appropriate.
 *
 * Verified via curl against staging on 2026-04-24:
 *   POST /auth/login/ with valid creds + no Authorization       → 200
 *   POST /auth/login/ with valid creds + bogus Authorization    → 401
 */
export const ANONYMOUS_ENDPOINTS: readonly string[] = [
  '/auth/login/',
  '/auth/register/',
  '/auth/password-reset/',
  '/auth/password-reset/confirm/',
  '/auth/verify-email/',
  '/auth/resend-verification/',
  '/auth/accept-invitation/',
] as const;

/**
 * True when `url` targets an endpoint in ANONYMOUS_ENDPOINTS.
 *
 * Matches by suffix because callers pass paths relative to baseURL
 * (e.g. `/auth/login/`) but absolute URLs are also possible
 * (e.g. `https://api.stagingmeshant-internal.example.com/api/v1/auth/login/`).
 * Query strings are tolerated (`?next=/foo`) by checking for the
 * substring plus a `?` sentinel.
 */
export function isAnonymousEndpoint(url: string): boolean {
  return ANONYMOUS_ENDPOINTS.some(
    (ep) => url === ep || url.endsWith(ep) || url.includes(`${ep}?`),
  );
}

export class ApiClient {
  _accessToken: string | null = null;
  _refreshToken: string | null = null;
  _refreshPromise: Promise<string> | null = null;
  _getTenantId: (() => string | null | undefined) | null = null;
  /**
   * When true, auth tokens are delivered via httpOnly cookies — the client
   * must NOT send ``Authorization: Bearer`` and must NOT store tokens in
   * memory/localStorage.  Detected automatically when the login response
   * does not contain ``access_token`` in the body (Phase 220.4).
   */
  _cookieAuthMode = false;
  readonly _baseURL: string;
  readonly _httpClient: InternalHttpClient;

  constructor() {
    this._baseURL = API_BASE_URL;
    this._httpClient = new InternalHttpClient(this);
    // Phase 226.F2 — pre-seed _cookieAuthMode from VITE_COOKIE_AUTH so the
    // chromium-cookie-auth Playwright project exercises the cookie path
    // before the first login response arrives. Hint only; the runtime
    // detector at authService.ts:47-51 still updates this flag based on
    // what login actually returns.
    try {
      const flag =
        typeof import.meta !== 'undefined' && import.meta.env
          ? (import.meta.env.VITE_COOKIE_AUTH as string | undefined)
          : undefined;
      if (flag === 'true' || flag === '1') {
        this._cookieAuthMode = true;
      }
    } catch {
      // intentional: import.meta may not be available in Jest/SSR; this constructor must NOT throw on legacy entry points. Cookie mode stays default-false in that case, runtime detector still updates it post-login.
    }
  }

  /**
   * Set a callback function to retrieve tenant ID.
   * This avoids circular dependencies with auth store.
   */
  setTenantIdGetter(getter: (() => string | null | undefined) | null): void {
    this._getTenantId = getter || null;
  }

  /**
   * Build headers for a specific HTTP method + URL.
   *
   * The URL is needed so we can skip the Authorization header for anonymous
   * endpoints (login, register, password reset, etc.). Attaching a stale
   * bearer to those endpoints causes the backend's auth middleware to
   * return 401 without reading the request body — see ANONYMOUS_ENDPOINTS.
   *
   * `url` is optional so existing callers that haven't been updated keep
   * working (the ApiClient still attaches the bearer, matching prior
   * behaviour when we can't check the URL). All InternalHttpClient code
   * paths pass the URL.
   */
  _buildHeaders(method: string, url?: string): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Auth token — skip for three reasons:
    //   1. Cookie mode (httpOnly cookies are sent automatically via
    //      credentials: 'include'; a Bearer header would be redundant and
    //      the token isn't available in JS anyway).
    //   2. No token in memory.
    //   3. URL targets an anonymous endpoint (login/register/...) where
    //      attaching a stale bearer would trigger a spurious 401.
    const skipAuthForAnonymous = url !== undefined && isAnonymousEndpoint(url);
    if (this._accessToken && !this._cookieAuthMode && !skipAuthForAnonymous) {
      headers['Authorization'] = `Bearer ${this._accessToken}`;
    }

    // Tenant ID
    if (this._getTenantId) {
      const tenantId = this._getTenantId();
      if (tenantId) {
        headers['X-Tenant-ID'] = tenantId;
      }
    }

    // CSRF token for state-changing requests (Phase 50.7)
    const upperMethod = method.toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(upperMethod)) {
      const csrfToken = readCsrfToken();
      if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
      }
    }

    // Prevent caching for GET requests
    if (upperMethod === 'GET') {
      headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
      headers['Pragma'] = 'no-cache';
    }

    return headers;
  }

  get baseURL(): string {
    return this._baseURL;
  }

  async _handleRefreshAndRetry<T>(
    url: string,
    method: string,
    data: unknown | undefined,
    config: RequestConfig | undefined,
  ): Promise<ApiResponse<T> | null> {
    // In cookie mode, refresh is always possible (httpOnly cookie sent automatically).
    // In legacy mode, we need either a refresh token or no access token (cold start).
    const canRefresh = this._cookieAuthMode || this._refreshToken || !this._accessToken;
    if (!canRefresh) {
      // No refresh token available — session is dead, force re-login
      this.clearTokens();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
      return null;
    }

    try {
      const newAccessToken = await this._refreshAccessToken();
      if (newAccessToken) {
        this.setAccessToken(newAccessToken);
      }
      // Retry original request with new token
      return this._httpClient._request<T>(url, method, data, config, true);
    } catch {
      // Refresh failed (400/401/network error) — session is unrecoverable.
      // Force re-login instead of leaving user stuck with UNKNOWN_ERROR.
      this.clearTokens();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
      return null;
    }
  }

  async _refreshAccessToken(): Promise<string> {
    if (this._refreshPromise) {
      return this._refreshPromise;
    }

    this._refreshPromise = (async () => {
      try {
        // In cookie mode, refresh_token cookie is sent automatically via
        // credentials: 'include'; no body payload needed.
        const body = this._cookieAuthMode
          ? undefined
          : JSON.stringify({ refresh_token: this._refreshToken });

        const response = await fetch(`${this._baseURL}/auth/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body,
          credentials: 'include',
        });

        if (!response.ok) {
          throw new Error(`Refresh failed with status ${response.status}`);
        }

        const responseData = (await response.json()) as {
          access_token?: string;
          refresh_token?: string;
        };

        // In cookie mode, tokens are in httpOnly cookies — not in body.
        // The browser handles cookie storage automatically.
        if (responseData.access_token) {
          this.setAccessToken(responseData.access_token);
        }
        if (responseData.refresh_token) {
          this.setRefreshToken(responseData.refresh_token);
        }

        // In cookie mode, return empty string (token is in cookie, not JS).
        return responseData.access_token || '';
      } finally {
        this._refreshPromise = null;
      }
    })();

    return this._refreshPromise;
  }

  getAccessToken(): string | null {
    return this._accessToken;
  }

  setAccessToken(token: string | null): void {
    // Phase 11.1: access_token lives in JS module memory only (never in localStorage).
    this._accessToken = token;
  }

  setRefreshToken(token: string | null): void {
    this._refreshToken = token;
    // Persist to localStorage in non-cookie mode so that rotations performed
    // silently by the 401-interceptor (_handleRefreshAndRetry → _refreshAccessToken)
    // survive a page reload. Without this, localStorage keeps the pre-rotation
    // token; the next reload reads it, presents a revoked token, and the backend
    // revokes the entire family → user is kicked to /login after any 4xx that
    // was followed by a reload. Cookie mode stores tokens in httpOnly cookies,
    // so localStorage must stay empty.
    if (typeof window !== 'undefined' && !this._cookieAuthMode) {
      try {
        if (token === null) {
          localStorage.removeItem('refresh_token');
        } else {
          localStorage.setItem('refresh_token', token);
        }
      } catch { /* SSR / disabled storage — memory-only is acceptable fallback */ }
    }
  }

  clearTokens(): void {
    this._accessToken = null;
    this._refreshToken = null;
    this._cookieAuthMode = false;
  }

  getClient(): HttpClient {
    return this._httpClient;
  }
}

/**
 * Internal HTTP client that implements HttpClient using fetch.
 * Keeps a reference to ApiClient for auth state and header building.
 */
class InternalHttpClient implements HttpClient {
  defaults: { baseURL: string };
  _apiClient: ApiClient;

  constructor(apiClient: ApiClient) {
    this._apiClient = apiClient;
    this.defaults = { baseURL: apiClient.baseURL };
  }

  async get<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this._request<T>(url, 'GET', undefined, config);
  }

  async head<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this._request<T>(url, 'HEAD', undefined, config);
  }

  async post<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this._request<T>(url, 'POST', data, config);
  }

  async put<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this._request<T>(url, 'PUT', data, config);
  }

  async patch<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this._request<T>(url, 'PATCH', data, config);
  }

  async delete<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this._request<T>(url, 'DELETE', undefined, config);
  }

  async _request<T>(
    url: string,
    method: string,
    data?: unknown,
    config?: RequestConfig,
    isRetryAfterRefresh = false,
    networkRetryCount = 0,
  ): Promise<ApiResponse<T>> {
    const correlationId = crypto.randomUUID();
    const startTime = performance.now();

    // Build full URL
    let fullUrl = url.startsWith('http')
      ? url
      : `${this._apiClient.baseURL}/${url}`.replace(/([^:])\/+/g, '$1/');

    // Append query params
    if (config?.params) {
      const searchParams = new URLSearchParams();
      for (const [k, v] of Object.entries(config.params)) {
        if (v !== undefined && v !== null) {
          searchParams.append(k, String(v));
        }
      }
      const qs = searchParams.toString();
      if (qs) {
        fullUrl += (fullUrl.includes('?') ? '&' : '?') + qs;
      }
    }

    // Build headers (method-aware: CSRF for POST, Cache-Control for GET;
    // URL-aware: skip Authorization for anonymous endpoints like /auth/login/).
    const baseHeaders = this._apiClient._buildHeaders(method, url);
    const headers = new Headers({
      ...baseHeaders,
      'X-Correlation-ID': correlationId,
      ...(config?.headers || {}),
    });

    // Don't set Content-Type for FormData (browser sets multipart boundary automatically)
    if (data instanceof FormData) {
      headers.delete('Content-Type');
    }

    // Timeout via AbortController
    const timeout = config?.timeout ?? 30000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const fetchInit: globalThis.RequestInit = {
      method,
      headers,
      credentials: 'include',
      signal: config?.signal ?? controller.signal,
    };

    // Body
    if (data !== undefined && data !== null) {
      fetchInit.body = data instanceof FormData ? data : JSON.stringify(data);
    }

    let response: Response;
    try {
      response = await fetch(fullUrl, fetchInit);
    } catch (err) {
      clearTimeout(timeoutId);

      // Timeout
      if (err instanceof DOMException && err.name === 'AbortError') {
        const apiError: ApiError = {
          error: {
            code: 'TIMEOUT',
            message: `Request timed out after ${timeout}ms`,
            http_status: 0,
            request_id: correlationId,
            timestamp: new Date().toISOString(),
          },
        };
        errorReportingService.reportError(apiError, { correlationId });
        throw apiError;
      }

      // Network error — retry for safe methods (max 2 retries with backoff)
      const isSafeMethod = ['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase());
      if (isSafeMethod && networkRetryCount < 2) {
        const delay = 1000 * (networkRetryCount + 1);
        await new Promise((r) => setTimeout(r, delay));
        return this._request<T>(url, method, data, config, isRetryAfterRefresh, networkRetryCount + 1);
      }

      // Non-retryable network error
      const apiError: ApiError = {
        error: {
          code: 'NETWORK_ERROR',
          message: err instanceof Error ? err.message : 'Network error',
          http_status: 0,
          request_id: correlationId,
          timestamp: new Date().toISOString(),
        },
      };
      errorReportingService.reportError(apiError, { correlationId });
      throw apiError;
    } finally {
      clearTimeout(timeoutId);
    }

    // Measure API call duration
    const duration = performance.now() - startTime;
    const responseCorrelationId =
      response.headers.get('x-correlation-id') ||
      response.headers.get('x-request-id') ||
      correlationId;
    performanceMetricsService.measureAPICall(url, duration, responseCorrelationId);

    // Success
    if (response.ok) {
      const responseData = await parseResponseBody<T>(response, config?.responseType);
      return {
        data: responseData,
        status: response.status,
        headers: headersToRecord(response.headers),
      };
    }

    // Error: parse body
    const errorBody = await response.json().catch(() => null);

    // 401 — try refresh token (once)
    if (response.status === 401 && !isRetryAfterRefresh) {
      const retryResult = await this._apiClient._handleRefreshAndRetry<T>(url, method, data, config);
      if (retryResult) return retryResult;
    }

    // Normalize and throw
    const normalizedError = normalizeApiError(errorBody, response.status, responseCorrelationId);
    const apiError: ApiError = { error: normalizedError };
    errorReportingService.reportError(apiError, { correlationId: responseCorrelationId });
    throw apiError;
  }
}

export const apiClient = new ApiClient();
