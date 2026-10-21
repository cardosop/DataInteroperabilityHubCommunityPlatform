/**
 * DataHub Client
 *
 * Main SDK client with authentication, error handling, and retry logic.
 *
 * W6.2 (oss-release-remediation R2-X2) — the client is implemented on
 * the platform `fetch` API; axios was evicted as a supply-chain risk
 * (repo policy, CLAUDE.md).  The rewrite also fixes two shipped defects:
 *
 *  1. 401 refresh loop — the old axios response interceptor retried a
 *     401 through the interceptor chain again, so a server that kept
 *     returning 401 (e.g. a refresh callback returning a stale token)
 *     recursed unboundedly.  The refresh is now capped at ONE attempt
 *     per logical request; a second 401 surfaces as UnauthorizedError.
 *
 *  2. Retry-After never read — the 429/503 backoff used plain
 *     exponential backoff and never consulted the real `Retry-After`
 *     header (parseError received response DATA, not headers, so the
 *     parse branch was dead code).  The retry delay is now at least the
 *     server's Retry-After (seconds or HTTP-date).
 */

import { DataHubClientConfig, DEFAULT_CONFIG } from './config';
import { camelToSnake, snakeToCamel } from './caseTransform';
import { ContractsAPI } from './contracts';
import { LineageAPI } from './lineage';
import { ComplianceAPI } from './compliance';
import { GovernanceAPI } from './governance';
import { MeshAPI } from './mesh';
import { VirtualizationAPI } from './virtualization';
import { WebhooksAPI } from './webhooks';
import { MarketplaceAPI } from './marketplace';
import { BaaSAPI } from './baas';
import { MLAPI } from './ml';
import { ScheduledIngestionAPI } from './scheduledIngestion';
import { ScheduledExportAPI } from './scheduledExport';
import { VersioningAPI } from './versioning';
import { BillingAPI } from './billing';
import { SearchAPI } from './search';
import { ObservabilityAPI } from './observability';
import { GDPRAPI } from './gdpr';
import { TenantsAPI } from './tenants';
import { TransformationAPI } from './transformation';
import { SemanticAPI } from './semantic';
import { DatasetsAPI } from './datasets';
import { AssetsAPI } from './assets';
import { FilesAPI } from './files';
import { DQAPI } from './dq';
import { WorkflowsAPI } from './workflows';

import {
  DataHubError,
  parseError,
  NetworkError,
  UnauthorizedError,
} from './errors';

/** Options for a single request. */
export interface RequestOptions {
  /** Query-string parameters (keys are sent as provided — the API
   * modules already map camelCase params to snake_case themselves). */
  params?: Record<string, any>;
  /** Extra headers; the configured Authorization header always wins. */
  headers?: Record<string, string>;
  /** Per-request retry budget; defaults to config.maxRetries. */
  retries?: number;
  /** Per-request timeout in ms; defaults to config.timeout. */
  timeout?: number;
  /** Response decoding: 'json' (default), 'text', or 'arraybuffer'. */
  responseType?: 'json' | 'text' | 'arraybuffer';
}

/** Internal options carrying the request body through to send(). */
interface SendOptions extends RequestOptions {
  body?: any;
}

/** Normalised response returned by {@link DataHubClient.request}. */
export interface DataHubResponse<T = any> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

/**
 * Exponential backoff delay calculation.
 *
 * When *retryAfterSeconds* is provided (the server's `Retry-After`
 * hint), the delay is at least that long — the server told us how long
 * to wait, and exponential backoff alone is often not enough.
 */
export function calculateBackoffDelay(
  attempt: number,
  baseDelayMs: number = 1000,
  retryAfterSeconds?: number
): number {
  const base = baseDelayMs * Math.pow(2, attempt);
  if (retryAfterSeconds !== undefined && retryAfterSeconds > 0) {
    return Math.max(base, retryAfterSeconds * 1000);
  }
  return base;
}

/**
 * Check if error is retryable.
 */
export function isRetryableError(error: DataHubError): boolean {
  // Network errors (httpStatus 0, NETWORK_ERROR) are retryable.
  if (error.code === 'NETWORK_ERROR') {
    return true;
  }
  // Retry on 5xx errors and 429 (rate limit).
  return error.httpStatus >= 500 || error.httpStatus === 429;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Main DataHub Client
 */
export class DataHubClient {
  private config: DataHubClientConfig;
  private tokenRefreshCallback?: () => Promise<string>;

  // 118C.4: Token refresh lock — prevents concurrent refresh races.
  private refreshPromise: Promise<string> | null = null;

  constructor(config: DataHubClientConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    if (!this.config.baseUrl) {
      throw new Error('baseUrl is required');
    }

    // Initialize API modules
    this.initializeAPIs();
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
   * Get current configuration
   */
  getConfig(): Readonly<DataHubClientConfig> {
    return { ...this.config };
  }

  /**
   * Make HTTP request with retry logic.
   *
   * A 401 triggers at most ONE token-refresh retry per logical request
   * (the 401-loop cap).  Transient errors (5xx, 429, network failures)
   * retry up to `retries`, with exponential backoff that honours the
   * server's `Retry-After` header when present.
   */
  async request<T = any>(
    method: string,
    path: string,
    options: RequestOptions = {}
  ): Promise<DataHubResponse<T>> {
    return this.requestWithBody<T>(method, path, undefined, options);
  }

  private async requestWithBody<T>(
    method: string,
    path: string,
    body: any,
    options: RequestOptions
  ): Promise<DataHubResponse<T>> {
    const sendOptions: SendOptions = { ...options, body };
    const maxRetries = options.retries ?? this.config.maxRetries ?? 3;
    const backoffBaseMs = this.config.backoffBaseMs ?? 1000;
    // 401-refresh attempt cap: at most one refresh per logical request.
    let tokenRefreshed = false;
    // Transient-error retry budget, tracked separately so the refresh
    // retry never consumes it (a 401 + refresh must retry even when
    // maxRetries is 0).
    let attempt = 0;

    for (;;) {
      if (this.config.enableLogging) {
        console.log(
          `[DataHub SDK] ${method.toUpperCase()} ${path} (attempt ${attempt + 1})`
        );
      }

      let response: Response;
      try {
        response = await this.send(method, path, sendOptions);
      } catch (error: any) {
        const networkError =
          error instanceof NetworkError
            ? error
            : new NetworkError(error?.message || String(error));
        if (attempt >= maxRetries) {
          throw networkError;
        }
        await sleep(calculateBackoffDelay(attempt, backoffBaseMs));
        attempt++;
        continue;
      }

      // 401 → refresh (once) and retry without consuming the retry
      // budget; a second 401 falls through to the error path below.
      if (
        response.status === 401 &&
        this.tokenRefreshCallback &&
        !tokenRefreshed
      ) {
        try {
          const newToken = await this.refreshTokenOnce();
          this.config.apiToken = newToken;
          tokenRefreshed = true;
          continue;
        } catch (error) {
          throw error instanceof UnauthorizedError
            ? error
            : new UnauthorizedError('Token refresh failed');
        }
      }

      if (response.status >= 200 && response.status < 300) {
        return await this.parseResponse<T>(response, options);
      }

      const error = await this.toError(response);
      if (attempt >= maxRetries || !isRetryableError(error)) {
        throw error;
      }
      const retryAfter =
        typeof error.retryAfter === 'number' ? error.retryAfter : undefined;
      await sleep(calculateBackoffDelay(attempt, backoffBaseMs, retryAfter));
      attempt++;
    }
  }

  /**
   * GET request
   */
  async get<T = any>(url: string, options?: RequestOptions): Promise<T> {
    const response = await this.request<T>('GET', url, options);
    return response.data;
  }

  /**
   * POST request
   */
  async post<T = any>(
    url: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    const response = await this.requestWithBody<T>(
      'POST',
      url,
      data,
      options ?? {}
    );
    return response.data;
  }

  /**
   * PATCH request
   */
  async patch<T = any>(
    url: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    const response = await this.requestWithBody<T>(
      'PATCH',
      url,
      data,
      options ?? {}
    );
    return response.data;
  }

  /**
   * DELETE request
   */
  async delete<T = any>(url: string, options?: RequestOptions): Promise<T> {
    const response = await this.request<T>('DELETE', url, options);
    return response.data;
  }

  /**
   * Build the absolute URL from the configured base and the request
   * path/query.  The base path (e.g. /api/v1) is preserved even when
   * the request path starts with a slash — the axios client's
   * combineURLs semantics this SDK shipped with.
   */
  private buildUrl(path: string, params?: Record<string, any>): string {
    const base = `${this.config.baseUrl.replace(/\/+$/, '')}/`;
    const cleanPath = path.replace(/^\/+/, '');
    const url = new URL(cleanPath, base);
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value === undefined || value === null) {
          continue;
        }
        url.searchParams.set(key, String(value));
      }
    }
    return url.toString();
  }

  /**
   * Perform one wire round-trip with fetch (no retries here).
   */
  private async send(
    method: string,
    path: string,
    options: SendOptions
  ): Promise<Response> {
    const headers: Record<string, string> = {
      'User-Agent': this.config.userAgent || 'datahub-interoperability-sdk',
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.config.apiToken) {
      // 118C.1: bearer by default, ApiKey header for api-key auth.
      const prefix = this.config.authType === 'apikey' ? 'ApiKey' : 'Bearer';
      headers.Authorization = `${prefix} ${this.config.apiToken}`;
    }

    const init: RequestInit = { method, headers };

    if (options.body !== undefined && options.body !== null) {
      // 118C.2: request bodies are camelCase → snake_case.
      init.body = JSON.stringify(camelToSnake(options.body));
    }

    const timeout = options.timeout ?? this.config.timeout;
    if (timeout && timeout > 0) {
      init.signal = AbortSignal.timeout(timeout);
    }

    try {
      return await fetch(this.buildUrl(path, options.params), init);
    } catch (error: any) {
      if (error?.name === 'TimeoutError' || error?.name === 'AbortError') {
        throw new NetworkError(
          `Request timed out after ${timeout ?? this.config.timeout}ms`
        );
      }
      throw new NetworkError(error?.message || 'Network request failed');
    }
  }

  /**
   * Single-flight token refresh (118C.4): concurrent 401s share one
   * callback invocation; a failure rejects every waiter.
   */
  private refreshTokenOnce(): Promise<string> {
    if (!this.refreshPromise) {
      const refresh = this.tokenRefreshCallback!().finally(() => {
        this.refreshPromise = null;
      });
      this.refreshPromise = refresh;
    }
    return this.refreshPromise.then((token) => {
      if (!token) {
        throw new UnauthorizedError('Token refresh failed');
      }
      return token;
    });
  }

  /**
   * Decode a successful response body.
   */
  private async parseResponse<T>(
    response: Response,
    options: RequestOptions
  ): Promise<DataHubResponse<T>> {
    const headers: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      headers[key.toLowerCase()] = value;
    });

    if (options.responseType === 'arraybuffer') {
      return {
        data: Buffer.from(await response.arrayBuffer()) as any,
        status: response.status,
        headers,
      };
    }
    if (options.responseType === 'text') {
      return {
        data: (await response.text()) as any,
        status: response.status,
        headers,
      };
    }

    const text = await response.text();
    if (!text) {
      return { data: undefined as any, status: response.status, headers };
    }
    const contentType = headers['content-type'] || '';
    if (contentType.includes('json')) {
      // 118C.3: response bodies are snake_case → camelCase.
      return {
        data: snakeToCamel(JSON.parse(text)) as T,
        status: response.status,
        headers,
      };
    }
    return { data: text as any, status: response.status, headers };
  }

  /**
   * Convert an error response into the right DataHubError subclass,
   * passing the REAL response headers through so `Retry-After` is read
   * (the axios version fed parseError the response DATA, so the header
   * never reached it).
   */
  private async toError(response: Response): Promise<DataHubError> {
    const headers: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      headers[key.toLowerCase()] = value;
    });

    const text = await response.text();
    if (text) {
      const contentType = headers['content-type'] || '';
      if (contentType.includes('json')) {
        try {
          const payload = JSON.parse(text);
          if (payload && typeof payload === 'object') {
            const parsed = parseError(payload, headers, response.status);
            if (parsed) {
              return parsed;
            }
          }
        } catch {
          // Not JSON — fall through to the generic HTTP error below.
        }
      }
    }

    return new DataHubError(
      `HTTP ${response.status}: ${text || response.statusText}`,
      'HTTP_ERROR',
      response.status
    );
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
    // The API modules import DataHubClient as a TYPE only, so these
    // top-level imports create no runtime cycle (W6.2 — the axios
    // client used lazy require() here for the same reason).
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
