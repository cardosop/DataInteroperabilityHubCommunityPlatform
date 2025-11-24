/**
 * DataHub Client
 * 
 * Main SDK client with authentication, error handling, and retry logic.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { DataHubClientConfig, DEFAULT_CONFIG } from './config';
import {
  DataHubError,
  parseError,
  NetworkError,
  UnauthorizedError,
} from './errors';

/**
 * Exponential backoff delay calculation
 */
function calculateBackoffDelay(attempt: number, baseDelay: number = 1000): number {
  return baseDelay * Math.pow(2, attempt);
}

/**
 * Check if error is retryable
 */
function isRetryableError(error: any): boolean {
  if (!error.response) {
    // Network error - retryable
    return true;
  }
  
  const status = error.response.status;
  // Retry on 5xx errors and 429 (rate limit)
  return status >= 500 || status === 429;
}

/**
 * Main DataHub Client
 */
export class DataHubClient {
  private axiosInstance: AxiosInstance;
  private config: DataHubClientConfig;
  private tokenRefreshCallback?: () => Promise<string>;

  constructor(config: DataHubClientConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    
    if (!this.config.baseUrl) {
      throw new Error('baseUrl is required');
    }

    // Create axios instance
    this.axiosInstance = axios.create({
      baseURL: this.config.baseUrl,
      timeout: this.config.timeout,
      headers: {
        'User-Agent': this.config.userAgent,
        'Content-Type': 'application/json',
      },
    });

    // Set up request interceptor for authentication
    this.axiosInstance.interceptors.request.use(
      (config) => {
        if (this.config.apiToken) {
          config.headers.Authorization = `Bearer ${this.config.apiToken}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Set up response interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        // Handle token refresh for 401 errors
        if (error.response?.status === 401 && this.tokenRefreshCallback) {
          try {
            const newToken = await this.tokenRefreshCallback();
            this.config.apiToken = newToken;
            // Retry the original request
            if (error.config) {
              error.config.headers.Authorization = `Bearer ${newToken}`;
              return this.axiosInstance.request(error.config);
            }
          } catch (refreshError) {
            // Token refresh failed
            throw new UnauthorizedError('Token refresh failed');
          }
        }

        // Parse and throw appropriate error
        if (error.response) {
          throw parseError(error.response.data);
        } else if (error.request) {
          throw new NetworkError(error.message || 'Network request failed');
        } else {
          throw new DataHubError(
            error.message || 'Request failed',
            'REQUEST_ERROR',
            0
          );
        }
      }
    );
  }

  /**
   * Set API token
   */
  setApiToken(token: string): void {
    this.config.apiToken = token;
  }

  /**
   * Set token refresh callback
   */
  setTokenRefreshCallback(callback: () => Promise<string>): void {
    this.tokenRefreshCallback = callback;
  }

  /**
   * Make HTTP request with retry logic
   */
  async request<T = any>(
    config: AxiosRequestConfig,
    options?: { retries?: number }
  ): Promise<AxiosResponse<T>> {
    const maxRetries = options?.retries ?? this.config.maxRetries ?? 3;
    let lastError: any;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        if (this.config.enableLogging) {
          console.log(`[DataHub SDK] ${config.method?.toUpperCase()} ${config.url} (attempt ${attempt + 1})`);
        }

        const response = await this.axiosInstance.request<T>(config);
        return response;
      } catch (error: any) {
        lastError = error;

        // Don't retry on last attempt or non-retryable errors
        if (attempt >= maxRetries || !isRetryableError(error)) {
          throw error;
        }

        // Calculate backoff delay
        const delay = calculateBackoffDelay(attempt);
        
        if (this.config.enableLogging) {
          console.log(`[DataHub SDK] Retrying after ${delay}ms...`);
        }

        // Wait before retry
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    throw lastError;
  }

  /**
   * GET request
   */
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.request<T>({ ...config, method: 'GET', url });
    return response.data;
  }

  /**
   * POST request
   */
  async post<T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.request<T>({
      ...config,
      method: 'POST',
      url,
      data,
    });
    return response.data;
  }

  /**
   * PATCH request
   */
  async patch<T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.request<T>({
      ...config,
      method: 'PATCH',
      url,
      data,
    });
    return response.data;
  }

  /**
   * DELETE request
   */
  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.request<T>({
      ...config,
      method: 'DELETE',
      url,
    });
    return response.data;
  }

  /**
   * Get axios instance (for advanced usage)
   */
  getAxiosInstance(): AxiosInstance {
    return this.axiosInstance;
  }

  /**
   * Get current configuration
   */
  getConfig(): Readonly<DataHubClientConfig> {
    return { ...this.config };
  }
}

