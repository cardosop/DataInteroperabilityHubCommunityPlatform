/**
 * API Client
 * Axios instance with interceptors for auth, error handling, and correlation IDs
 */

import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import axios from 'axios';
import { errorReportingService } from '../services/errorReporting';
import { performanceMetricsService } from '../services/performanceMetrics';
import type { ApiError } from '../types/api';

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
      async (error: AxiosError<ApiError>) => {
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
        const correlationId =
          error.response?.headers['x-correlation-id'] ||
          error.response?.headers['x-request-id'] ||
          error.response?.data?.error?.request_id ||
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
        const responseData = error.response?.data;
        let normalizedError: ApiError['error'];

        if (
          responseData?.error &&
          typeof responseData.error === 'object' &&
          'code' in responseData.error
        ) {
          // Nested shape: { error: { code: string, message: string, ... } }
          normalizedError = {
            code: responseData.error.code || 'UNKNOWN_ERROR',
            message: responseData.error.message || error.message || 'An error occurred',
            http_status: error.response?.status || 500,
            request_id: correlationId || responseData.error.request_id || 'unknown',
            timestamp: responseData.error.timestamp || new Date().toISOString(),
            details: responseData.error.details,
            field_errors: responseData.error.field_errors,
          };
        } else if (responseData?.error || responseData?.code) {
          // Flat shape: { error: string, code: string, details: object }
          normalizedError = {
            code: responseData.code || 'UNKNOWN_ERROR',
            message:
              typeof responseData.error === 'string'
                ? responseData.error
                : error.message || 'An error occurred',
            http_status: error.response?.status || 500,
            request_id: correlationId || 'unknown',
            timestamp: responseData.timestamp || new Date().toISOString(),
            details:
              responseData.details ||
              (typeof responseData.error === 'object' &&
              responseData.error !== null &&
              !Array.isArray(responseData.error)
                ? responseData.error
                : undefined),
            field_errors: responseData.field_errors,
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
