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

// Use relative URL in browser to leverage Vite proxy, or full URL if explicitly set
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' ? '/api/v1' : 'http://localhost:8000/api/v1');

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
          _correlationId?: string;
        };

        // Handle 401 Unauthorized - try refresh token
        if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
          originalRequest._retry = true;

          try {
            const newAccessToken = await this.refreshAccessToken();
            this.setAccessToken(newAccessToken);
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - clear tokens and redirect to login
            this.clearTokens();
            window.location.href = '/login';
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
          const r = responseData as Record<string, unknown>;
          const detailMsg = typeof r.detail === 'string' ? r.detail : undefined;
          const errorMsg = typeof r.error === 'string' ? r.error : undefined;
          normalizedError = {
            code: (r.code as string) || 'UNKNOWN_ERROR',
            message:
              errorMsg ?? detailMsg ?? error.message ?? 'An error occurred',
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
        const response = await axios.post<{ access_token: string; refresh_token: string }>(
          `${API_BASE_URL}/auth/refresh/`,
          { refresh_token: this.refreshToken }
        );

        this.setAccessToken(response.data.access_token);
        if (response.data.refresh_token) {
          this.setRefreshToken(response.data.refresh_token);
        }

        return response.data.access_token;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  setAccessToken(token: string | null): void {
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
