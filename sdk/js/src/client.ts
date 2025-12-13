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
  // Check if it's a transformed DataHubError (has httpStatus property)
  if (error.httpStatus !== undefined) {
    const status = error.httpStatus;
    // Retry on 5xx errors and 429 (rate limit)
    return status >= 500 || status === 429;
  }
  
  // Check if it's an axios error with response
  if (error.response) {
    const status = error.response.status;
    // Retry on 5xx errors and 429 (rate limit)
    return status >= 500 || status === 429;
  }
  
  // Network error (no response) - retryable
  return true;
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

    // Initialize API modules
    this.initializeAPIs();

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

  // API modules
  contracts: any;
  lineage: any;
  scheduledIngestion: any;
  versioning: any;
  governance: any;
  search: any;
  observability: any;
  webhooks: any;

  /**
   * Initialize API modules
   */
  private initializeAPIs(): void {
    // Import and initialize API modules
    // Using dynamic imports to avoid circular dependencies
    const { ContractsAPI } = require('./contracts');
    const { LineageAPI } = require('./lineage');
    // Note: Other APIs will be added as they are created
    
    this.contracts = new ContractsAPI(this);
    this.lineage = new LineageAPI(this);
    // Initialize other APIs when modules are created
    // this.scheduledIngestion = new ScheduledIngestionAPI(this);
    // this.versioning = new VersioningAPI(this);
    // this.governance = new GovernanceAPI(this);
    // this.search = new SearchAPI(this);
    // this.observability = new ObservabilityAPI(this);
    // this.webhooks = new WebhooksAPI(this);
  }
}

