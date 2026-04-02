/**
 * DataHub Client
 *
 * Main SDK client with authentication, error handling, and retry logic.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { DataHubClientConfig, DEFAULT_CONFIG } from './config';
import { camelToSnake, snakeToCamel } from './caseTransform';
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

  // 118C.4: Token refresh lock — prevents concurrent refresh races
  private refreshPromise: Promise<string> | null = null;

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

    // 118C.1: Auth interceptor — supports bearer and apikey
    this.axiosInstance.interceptors.request.use(
      (reqConfig) => {
        if (this.config.apiToken) {
          const prefix =
            this.config.authType === 'apikey' ? 'ApiKey' : 'Bearer';
          reqConfig.headers.Authorization =
            `${prefix} ${this.config.apiToken}`;
        }
        return reqConfig;
      },
      (error) => Promise.reject(error)
    );

    // 118C.2: Request case transform — camelCase → snake_case
    this.axiosInstance.interceptors.request.use(
      (reqConfig) => {
        if (reqConfig.data && typeof reqConfig.data === 'object') {
          reqConfig.data = camelToSnake(reqConfig.data);
        }
        return reqConfig;
      },
      (error) => Promise.reject(error)
    );

    // Initialize API modules
    this.initializeAPIs();

    // Response interceptors: case transform + error handling
    this.axiosInstance.interceptors.response.use(
      // 118C.3: Response case transform — snake_case → camelCase
      (response: AxiosResponse) => {
        if (response.data && typeof response.data === 'object') {
          response.data = snakeToCamel(response.data);
        }
        return response;
      },
      // 118C.4: Error handler with serialized token refresh
      async (error: AxiosError) => {
        // Handle token refresh for 401 errors
        if (error.response?.status === 401 && this.tokenRefreshCallback) {
          try {
            // Serialize: if a refresh is already in flight, wait for it
            if (!this.refreshPromise) {
              this.refreshPromise = this.tokenRefreshCallback();
            }
            const newToken = await this.refreshPromise;
            this.config.apiToken = newToken;
            this.refreshPromise = null;

            // Retry the original request
            if (error.config) {
              const prefix =
                this.config.authType === 'apikey' ? 'ApiKey' : 'Bearer';
              error.config.headers.Authorization =
                `${prefix} ${newToken}`;
              return this.axiosInstance.request(error.config);
            }
          } catch (refreshError) {
            this.refreshPromise = null;
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
  compliance: any;
  scheduledIngestion: any;
  scheduledExport: any;
  versioning: any;
  governance: any;
  search: any;
  observability: any;
  webhooks: any;
  marketplace: any;
  baas: any;
  ml: any;
  billing: any;
  gdpr: any;
  tenants: any;
  mesh: any;
  virtualization: any;
  transformation: any;
  semantic: any;
  datasets: any;
  assets: any;
  files: any;
  dq: any;
  workflows: any;

  /**
   * Initialize API modules
   */
  private initializeAPIs(): void {
    const { ContractsAPI } = require('./contracts');
    const { LineageAPI } = require('./lineage');
    const { ComplianceAPI } = require('./compliance');
    const { GovernanceAPI } = require('./governance');
    const { MeshAPI } = require('./mesh');
    const { VirtualizationAPI } = require('./virtualization');
    const { WebhooksAPI } = require('./webhooks');
    const { MarketplaceAPI } = require('./marketplace');
    const { BaaSAPI } = require('./baas');
    const { MLAPI } = require('./ml');
    const { ScheduledIngestionAPI } = require('./scheduledIngestion');
    const { ScheduledExportAPI } = require('./scheduledExport');
    const { VersioningAPI } = require('./versioning');
    const { BillingAPI } = require('./billing');
    const { SearchAPI } = require('./search');
    const { ObservabilityAPI } = require('./observability');
    const { GDPRAPI } = require('./gdpr');
    const { TenantsAPI } = require('./tenants');
    const { TransformationAPI } = require('./transformation');
    const { SemanticAPI } = require('./semantic');
    const { DatasetsAPI } = require('./datasets');
    const { AssetsAPI } = require('./assets');
    const { FilesAPI } = require('./files');
    const { DQAPI } = require('./dq');
    const { WorkflowsAPI } = require('./workflows');

    this.contracts = new ContractsAPI(this);
    this.lineage = new LineageAPI(this);
    this.compliance = new ComplianceAPI(this);
    this.governance = new GovernanceAPI(this);
    this.mesh = new MeshAPI(this);
    this.virtualization = new VirtualizationAPI(this);
    this.webhooks = new WebhooksAPI(this);
    this.marketplace = new MarketplaceAPI(this);
    this.baas = new BaaSAPI(this);
    this.ml = new MLAPI(this);
    this.scheduledIngestion = new ScheduledIngestionAPI(this);
    this.scheduledExport = new ScheduledExportAPI(this);
    this.versioning = new VersioningAPI(this);
    this.billing = new BillingAPI(this);
    this.search = new SearchAPI(this);
    this.observability = new ObservabilityAPI(this);
    this.gdpr = new GDPRAPI(this);
    this.tenants = new TenantsAPI(this);
    this.transformation = new TransformationAPI(this);
    this.semantic = new SemanticAPI(this);
    this.datasets = new DatasetsAPI(this);
    this.assets = new AssetsAPI(this);
    this.files = new FilesAPI(this);
    this.dq = new DQAPI(this);
    this.workflows = new WorkflowsAPI(this);
  }
}

