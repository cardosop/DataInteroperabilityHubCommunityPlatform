/**
 * Test Environment Configuration for JavaScript SDK Tests
 * 
 * This module provides utilities for configuring the test environment
 * for JavaScript SDK tests, including API URL detection and service health checks.
 */

export interface TestEnvConfig {
  apiUrl: string;
  apiToken?: string;
  timeout?: number;
  maxRetries?: number;
}

export interface ServiceUrls {
  datacontract: string;
  dq: string;
  compliance: string;
  semantic: string;
  fuseki: string;
}

/**
 * Get the test API URL from environment variables or defaults.
 * 
 * Priority:
 * 1. TEST_API_URL environment variable
 * 2. API_SERVICE_URL environment variable
 * 3. API_TEST_PORT environment variable (constructs URL)
 * 4. Default: http://localhost:8001 (test environment default)
 * 
 * @returns API base URL for testing
 */
export function getTestApiUrl(): string {
  // Check explicit test API URL
  const apiUrl = process.env.TEST_API_URL || process.env.API_SERVICE_URL;
  if (apiUrl) {
    return apiUrl.replace(/\/$/, '');
  }

  // Check for test port configuration
  const testPort = process.env.API_TEST_PORT || '8001';
  return `http://localhost:${testPort}`;
}

/**
 * Get the full API base URL including /api/v1 prefix.
 * 
 * @returns Full API base URL (e.g., http://localhost:8001/api/v1)
 */
export function getTestApiBaseUrl(): string {
  const baseUrl = getTestApiUrl();
  if (!baseUrl.endsWith('/api/v1')) {
    return `${baseUrl}/api/v1`;
  }
  return baseUrl;
}

/**
 * Check if we're running in a test environment.
 * 
 * @returns True if test environment is detected
 */
export function isTestEnvironment(): boolean {
  const env = (process.env.ENVIRONMENT || '').toLowerCase();
  const testEnv = (process.env.TEST_ENV || '').toLowerCase();
  return env === 'test' || testEnv === 'true';
}

/**
 * Get test environment configuration.
 * 
 * @returns Test environment configuration
 */
export function getTestEnvConfig(): TestEnvConfig {
  return {
    apiUrl: getTestApiBaseUrl(),
    apiToken: process.env.TEST_API_TOKEN || process.env.API_TOKEN,
    timeout: parseInt(process.env.TEST_TIMEOUT || '30000', 10),
    maxRetries: parseInt(process.env.TEST_MAX_RETRIES || '3', 10),
  };
}

/**
 * Get test service URLs for all microservices.
 * 
 * @returns Dictionary mapping service names to URLs
 */
export function getTestServiceUrls(): ServiceUrls {
  return {
    datacontract: process.env.DATACONTRACT_SERVICE_URL || 'http://localhost:8093',
    dq: process.env.DQ_SERVICE_URL || 'http://localhost:8084',
    compliance: process.env.COMPLIANCE_SERVICE_URL || 'http://localhost:8085',
    semantic: process.env.SEMANTIC_SERVICE_URL || 'http://localhost:8086',
    fuseki: process.env.FUSEKI_URL || 'http://localhost:3031',
  };
}

/**
 * Check if a service is available by making a health check request.
 * 
 * @param url Service health check URL
 * @returns Promise that resolves to true if service is available
 */
export async function checkServiceHealth(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch (error) {
    return false;
  }
}

/**
 * Wait for a service to become available.
 * 
 * @param url Service health check URL
 * @param maxAttempts Maximum number of attempts
 * @param delayMs Delay between attempts in milliseconds
 * @returns Promise that resolves when service is available or rejects on timeout
 */
export async function waitForService(
  url: string,
  maxAttempts: number = 30,
  delayMs: number = 1000
): Promise<void> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (await checkServiceHealth(url)) {
      return;
    }
    if (attempt < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }
  throw new Error(`Service at ${url} did not become available within timeout`);
}
