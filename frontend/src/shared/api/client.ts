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

  return {
    code: 'UNKNOWN_ERROR',
    message: 'An error occurred',
    http_status: httpStatus,
    request_id: correlationId || 'unknown',
    timestamp: new Date().toISOString(),
    details: responseData ? { raw: responseData } : undefined,
  };
}

export class ApiClient {
  _accessToken: string | null = null;
  _refreshToken: string | null = null;
  _refreshPromise: Promise<string> | null = null;
  _getTenantId: (() => string | null | undefined) | null = null;
  readonly _baseURL: string;
  readonly _httpClient: InternalHttpClient;

  constructor() {
    this._baseURL = API_BASE_URL;
    this._httpClient = new InternalHttpClient(this);
  }

  /**
   * Set a callback function to retrieve tenant ID.
   * This avoids circular dependencies with auth store.
   */
  setTenantIdGetter(getter: (() => string | null | undefined) | null): void {
    this._getTenantId = getter || null;
  }

  /** Build headers for a specific HTTP method */
  _buildHeaders(method: string): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Auth token
    if (this._accessToken) {
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
    const canRefresh = this._refreshToken || !this._accessToken;
    if (!canRefresh) return null;

    try {
      const newAccessToken = await this._refreshAccessToken();
      if (newAccessToken) {
        this.setAccessToken(newAccessToken);
      }
      // Retry original request with new token
      return this._httpClient._request<T>(url, method, data, config, true);
    } catch {
      this.clearTokens();
      return null;
    }
  }

  async _refreshAccessToken(): Promise<string> {
    if (this._refreshPromise) {
      return this._refreshPromise;
    }

    this._refreshPromise = (async () => {
      try {
        const response = await fetch(`${this._baseURL}/auth/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: this._refreshToken }),
          credentials: 'include',
        });

        if (!response.ok) {
          throw new Error(`Refresh failed with status ${response.status}`);
        }

        const responseData = (await response.json()) as {
          access_token?: string;
          refresh_token?: string;
        };

        if (responseData.access_token) {
          this.setAccessToken(responseData.access_token);
        }
        if (responseData.refresh_token) {
          this.setRefreshToken(responseData.refresh_token);
        }

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
  }

  clearTokens(): void {
    this._accessToken = null;
    this._refreshToken = null;
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

    // Build headers (method-aware: CSRF for POST, Cache-Control for GET)
    const baseHeaders = this._apiClient._buildHeaders(method);
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
