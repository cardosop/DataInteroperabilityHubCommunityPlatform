/**
 * API Client
 * Axios instance with interceptors for auth, error handling, and correlation IDs
 */

import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import axios from 'axios';
import { errorReportingService } from '../services/errorReporting';
import { performanceMetricsService } from '../services/performanceMetrics';
import type { ApiError } from '../types/api';

/** Raw API error response - backend may return nested { error: {...} } or flat { error, code, ... } */
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

// Use relative URL in browser to leverage Vite proxy, or full URL if explicitly set
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  '/api/v1';

export class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<string> | null = null;
  private getTenantId: (() => string | null | undefined) | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
      withCredentials: true,  // Phase 90: send httpOnly cookies with requests
    });

    this.setupInterceptors();
  }

  /**
   * Set a callback function to retrieve tenant ID
   * This avoids circular dependencies with auth store
   */
  setTenantIdGetter(getter: (() => string | null | undefined) | null): void {
    this.getTenantId = getter || null;
  }

  private setupInterceptors(): void {
    // Request interceptor - add auth token, tenant ID, and correlation ID
    this.client.interceptors.request.use(
      (config) => {
        const startTime = performance.now();

        // Add CSRF token for state-changing requests (Phase 50.7)
        const method = config.method?.toUpperCase() ?? '';
        if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
          const csrfToken = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
          if (csrfToken) {
            config.headers['X-CSRFToken'] = csrfToken;
          }
        }

        // Add auth token
        if (this.accessToken) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }

        // Add tenant ID header if authenticated
        if (this.getTenantId) {
          const tenantId = this.getTenantId();
          if (tenantId) {
            config.headers['X-Tenant-ID'] = tenantId;
          }
        }

        // Prevent caching for GET requests (ensures fresh data after mutations like activate)
        if (config.method?.toLowerCase() === 'get') {
          config.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
          config.headers['Pragma'] = 'no-cache';
        }

        // Add correlation ID (request ID for tracing)
        const correlationId = crypto.randomUUID();
        config.headers['X-Correlation-ID'] = correlationId;
        // Store correlation ID in a custom property
        (
          config as InternalAxiosRequestConfig & { _correlationId?: string; _startTime?: number }
        )._correlationId = correlationId;
        (config as InternalAxiosRequestConfig & { _startTime?: number })._startTime = startTime;

        return config;
      },
      (error) => {
        errorReportingService.reportError(error);
        return Promise.reject(error);
      }
    );

    // Response interceptor - handle errors and extract correlation ID
    this.client.interceptors.response.use(
      (response) => {
        // Extract correlation ID from response headers
        const correlationId =
          response.headers['x-correlation-id'] || response.headers['x-request-id'];
        if (correlationId) {
          (
            response.config as InternalAxiosRequestConfig & { _correlationId?: string }
          )._correlationId = correlationId;
        }

        // Measure API call duration
        const startTime = (response.config as InternalAxiosRequestConfig & { _startTime?: number })
          ._startTime;
        if (startTime) {
          const duration = performance.now() - startTime;
          const endpoint =
            response.config.url?.replace(response.config.baseURL || '', '') || 'unknown';
          performanceMetricsService.measureAPICall(endpoint, duration, correlationId);
        }

        return response;
      },
      async (error: AxiosError<RawErrorResponse>) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
          _retry?: boolean;
          _networkRetryCount?: number;
          _correlationId?: string;
        };

        // Retry on transient network errors (ECONNRESET, ERR_NETWORK, socket hang up) - common under E2E parallel load
        // Explicitly exclude ECONNABORTED: Axios uses it for request timeouts, which are not transient
        // network blips and must not be retried (especially for non-idempotent methods like POST).
        const isNetworkError =
          !error.response &&
          (error.code === 'ECONNRESET' ||
            error.code === 'ERR_NETWORK' ||
            error.code === 'ETIMEDOUT' ||
            /socket hang up|other side closed|network error/i.test(error.message || ''));
        const isSafeMethod = ['get', 'head', 'options'].includes(
          originalRequest.method?.toLowerCase() ?? ''
        );
        const retryCount = originalRequest._networkRetryCount ?? 0;
        const maxNetworkRetries = 2;
        if (isNetworkError && isSafeMethod && retryCount < maxNetworkRetries && originalRequest) {
          originalRequest._networkRetryCount = retryCount + 1;
          await new Promise((r) => setTimeout(r, 1000 * (retryCount + 1)));
          return this.client(originalRequest);
        }

        // Handle 401 Unauthorized - try refresh token
        // In cookie mode (Phase 90), refreshToken may be null since it's in httpOnly cookie,
        // so we also attempt refresh when accessToken is null (cookie-based auth).
        const canRefresh = this.refreshToken || !this.accessToken;
        if (error.response?.status === 401 && !originalRequest._retry && canRefresh) {
          originalRequest._retry = true;

          try {
            const newAccessToken = await this.refreshAccessToken();
            if (newAccessToken) {
              this.setAccessToken(newAccessToken);
              originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            }
            // In cookie mode, the browser sends the httpOnly cookie automatically
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed — clear in-memory tokens but do NOT hard-redirect to /login.
            // Hard redirect via window.location.href causes a full page reload that races
            // with authStore.initialize()'s proactive refresh, especially on initial load
            // when storageState provides a refresh_token but no access_token (Phase 11.1).
            // Instead, reject the promise so the caller (React Query, authStore) can handle
            // the failure gracefully (show error display, redirect via React Router, etc.).
            this.clearTokens();
            return Promise.reject(refreshError);
          }
        }

        // Extract correlation ID from error response
        const errData = error.response?.data as { error?: { request_id?: string } } | undefined;
        const correlationId =
          error.response?.headers['x-correlation-id'] ||
          error.response?.headers['x-request-id'] ||
          errData?.error?.request_id ||
          originalRequest._correlationId;

        if (correlationId) {
          originalRequest._correlationId = correlationId;
        }

        // Measure API call duration even on error
        const startTime = (originalRequest as InternalAxiosRequestConfig & { _startTime?: number })
          ._startTime;
        if (startTime) {
          const duration = performance.now() - startTime;
          const endpoint =
            originalRequest.url?.replace(originalRequest.baseURL || '', '') || 'unknown';
          performanceMetricsService.measureAPICall(endpoint, duration, correlationId);
        }

        // Normalize error shape
        // Handle both flat ({ error: string, code: string, details: object })
        // and nested ({ error: { code: string, message: string, ... } }) shapes
        const responseData = error.response?.data as RawErrorResponse | undefined;
        let normalizedError: ApiError['error'];

        const errObj = responseData?.error;
        const hasNested =
          errObj &&
          typeof errObj === 'object' &&
          !Array.isArray(errObj) &&
          'code' in errObj;

        if (hasNested) {
          // Nested shape: { error: { code: string, message: string, ... } }
          const e = errObj as ApiError['error'];
          normalizedError = {
            code: e.code || 'UNKNOWN_ERROR',
            message: e.message || error.message || 'An error occurred',
            http_status: error.response?.status || 500,
            request_id: correlationId || e.request_id || 'unknown',
            timestamp: e.timestamp || new Date().toISOString(),
            details: e.details,
            field_errors: e.field_errors,
          };
        } else if (responseData && typeof responseData === 'object') {
          // Flat shape: { error: string, code: string, details: object }
          // DRF 404 returns { detail: "Not found." } - use detail when error/code absent
          // DRF serializer validation returns { "field": ["message"] } - extract first message
          const r = responseData as Record<string, unknown>;
          const detailMsg = typeof r.detail === 'string' ? r.detail : undefined;
          const errorMsg = typeof r.error === 'string' ? r.error : undefined;
          const drfFieldMsg = extractFirstDrfFieldError(r);
          normalizedError = {
            code: (r.code as string) || 'UNKNOWN_ERROR',
            // Prefer human detail when both exist (e.g. Phase 204 login: error + code + detail)
            message:
              detailMsg ?? errorMsg ?? drfFieldMsg ?? error.message ?? 'An error occurred',
            http_status: error.response?.status || 500,
            request_id: correlationId || 'unknown',
            timestamp: (r.timestamp as string) || new Date().toISOString(),
            details:
              (r.details as Record<string, unknown>) ||
              (typeof r.error === 'object' &&
              r.error !== null &&
              !Array.isArray(r.error)
                ? (r.error as Record<string, unknown>)
                : undefined),
            field_errors: r.field_errors as ApiError['error']['field_errors'],
          };
        } else {
          // Fallback: no structured error data
          normalizedError = {
            code: 'UNKNOWN_ERROR',
            message: error.message || 'An error occurred',
            http_status: error.response?.status || 500,
            request_id: correlationId || 'unknown',
            timestamp: new Date().toISOString(),
            details: responseData ? { raw: responseData } : undefined,
          };
        }

        const apiError: ApiError = {
          error: normalizedError,
        };

        // Report error with correlation ID
        errorReportingService.reportError(apiError, {
          correlationId,
        });

        return Promise.reject(apiError);
      }
    );
  }

  private async refreshAccessToken(): Promise<string> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
      try {
        const response = await axios.post<{ access_token?: string; refresh_token?: string }>(
          `${API_BASE_URL}/auth/refresh/`,
          { refresh_token: this.refreshToken },
          { withCredentials: true },  // Phase 90: send httpOnly cookies
        );

        // If backend returns access_token in body (legacy mode), store it.
        // When USE_HTTPONLY_AUTH_COOKIES is enabled, access_token is in httpOnly
        // cookie and the browser handles it automatically via withCredentials.
        if (response.data.access_token) {
          this.setAccessToken(response.data.access_token);
        }
        if (response.data.refresh_token) {
          this.setRefreshToken(response.data.refresh_token);
        }

        return response.data.access_token || '';
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string | null): void {
    // Phase 11.1: access_token lives in JS module memory only (never in localStorage).
    // When USE_HTTPONLY_AUTH_COOKIES is enabled, access_token is in httpOnly cookie
    // and the browser handles it automatically via withCredentials.
    this.accessToken = token;
  }

  setRefreshToken(token: string | null): void {
    this.refreshToken = token;
  }

  clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
  }

  getClient(): AxiosInstance {
    return this.client;
  }
}

export const apiClient = new ApiClient();
