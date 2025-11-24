/**
 * SDK Configuration
 */

export interface DataHubClientConfig {
  /**
   * Base URL for the API (e.g., https://api.hub.example.com/api/v1)
   */
  baseUrl: string;
  
  /**
   * API token (JWT or API key) for authentication
   */
  apiToken?: string;
  
  /**
   * Request timeout in milliseconds (default: 30000)
   */
  timeout?: number;
  
  /**
   * Maximum number of retries for transient errors (default: 3)
   */
  maxRetries?: number;
  
  /**
   * Custom user agent string
   */
  userAgent?: string;
  
  /**
   * Enable request/response logging (default: false)
   */
  enableLogging?: boolean;
}

/**
 * Default configuration values
 */
export const DEFAULT_CONFIG: Partial<DataHubClientConfig> = {
  timeout: 30000,
  maxRetries: 3,
  userAgent: '@datahub/interoperability-sdk/1.0.0',
  enableLogging: false,
};

