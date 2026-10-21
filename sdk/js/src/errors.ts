/**
 * SDK Error Classes
 * 
 * Typed exceptions for API errors matching the standard error envelope.
 */

export interface ErrorDetails {
  [key: string]: any;
}

export interface APIErrorResponse {
  error: {
    code: string;
    message: string;
    http_status: number;
    request_id?: string;
    timestamp?: string;
    details?: ErrorDetails;
  };
}

/**
 * Base error class for all SDK errors
 */
export class DataHubError extends Error {
  public readonly code: string;
  public readonly httpStatus: number;
  public readonly requestId?: string;
  public readonly timestamp?: string;
  public readonly details?: ErrorDetails;
  /** Seconds to wait before retrying, from the response `Retry-After`
   * header (429/503).  W6.2 — the axios implementation never read the
   * real header because parseError received response DATA, not the
   * response headers. */
  public readonly retryAfter?: number;

  constructor(
    message: string,
    code: string,
    httpStatus: number,
    requestId?: string,
    timestamp?: string,
    details?: ErrorDetails,
    retryAfter?: number
  ) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.httpStatus = httpStatus;
    this.requestId = requestId;
    this.timestamp = timestamp;
    this.details = details;
    this.retryAfter = retryAfter;

    // Maintains proper stack trace for where our error was thrown
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  /**
   * Convert error to JSON-serializable object
   */
  toJSON(): APIErrorResponse {
    return {
      error: {
        code: this.code,
        message: this.message,
        http_status: this.httpStatus,
        request_id: this.requestId,
        timestamp: this.timestamp,
        details: this.details,
      },
    };
  }
}

/**
 * Validation error (400)
 */
export class ValidationError extends DataHubError {
  constructor(message: string, requestId?: string, timestamp?: string, details?: ErrorDetails) {
    super(message, 'VALIDATION_ERROR', 400, requestId, timestamp, details);
  }
}

/**
 * Authentication error (401)
 */
export class UnauthorizedError extends DataHubError {
  constructor(message: string = 'Authentication required', requestId?: string) {
    super(message, 'AUTH_UNAUTHORIZED', 401, requestId);
  }
}

/**
 * Authorization error (403)
 */
export class ForbiddenError extends DataHubError {
  constructor(message: string = 'Permission denied', requestId?: string) {
    super(message, 'AUTH_FORBIDDEN', 403, requestId);
  }
}

/**
 * Not found error (404)
 */
export class NotFoundError extends DataHubError {
  constructor(message: string = 'Resource not found', requestId?: string) {
    super(message, 'NOT_FOUND', 404, requestId);
  }
}

/**
 * Conflict error (409)
 */
export class ConflictError extends DataHubError {
  constructor(message: string, requestId?: string, details?: ErrorDetails) {
    super(message, 'CONFLICT_ERROR', 409, requestId, undefined, details);
  }
}

/**
 * Rate limit error (429)
 */
export class RateLimitError extends DataHubError {
  constructor(
    message: string,
    requestId?: string,
    retryAfter?: number
  ) {
    super(message, 'RATE_LIMIT_EXCEEDED', 429, requestId, undefined, undefined, retryAfter);
  }
}

/**
 * Server error (5xx)
 */
export class ServerError extends DataHubError {
  constructor(
    message: string,
    code: string = 'INTERNAL_ERROR',
    httpStatus: number = 500,
    requestId?: string,
    retryAfter?: number
  ) {
    super(message, code, httpStatus, requestId, undefined, undefined, retryAfter);
  }
}

/**
 * Network/timeout error
 */
export class NetworkError extends DataHubError {
  constructor(message: string = 'Network error occurred') {
    super(message, 'NETWORK_ERROR', 0);
  }
}

/**
 * Parse a `Retry-After` header value into seconds.
 *
 * Accepts both RFC 7231 forms: a delta-seconds integer ("120") and an
 * HTTP-date ("Wed, 21 Oct 2015 07:28:00 GMT").  Returns undefined when
 * the value is absent or unparseable.
 */
export function parseRetryAfter(
  value: string | undefined,
  now: number = Date.now()
): number | undefined {
  if (value === undefined || value === '') {
    return undefined;
  }
  const trimmed = value.trim();
  const seconds = Number(trimmed);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return seconds;
  }
  const date = Date.parse(trimmed);
  if (!Number.isNaN(date)) {
    return Math.max(0, Math.ceil((date - now) / 1000));
  }
  return undefined;
}

/**
 * Parse API error response and return appropriate error class.
 *
 * *response* is the error-envelope body; *headers* are the REAL
 * response headers (lower-cased keys) so `Retry-After` is honoured
 * (W6.2); *fallbackStatus* covers envelopes without an explicit
 * http_status.
 */
export function parseError(
  response: any,
  headers?: Record<string, string>,
  fallbackStatus?: number
): DataHubError | null {
  if (response?.error) {
    const error = response.error;
    const code = error.code || 'UNKNOWN_ERROR';
    const httpStatus = error.http_status || fallbackStatus || 500;
    const message = error.message || 'An error occurred';
    const requestId = error.request_id;
    const timestamp = error.timestamp;
    const details = error.details;
    const retryAfter = parseRetryAfter(headers?.['retry-after']);

    // Map error codes to specific error classes
    switch (httpStatus) {
      case 400:
        return new ValidationError(message, requestId, timestamp, details);
      case 401:
        return new UnauthorizedError(message, requestId);
      case 403:
        return new ForbiddenError(message, requestId);
      case 404:
        return new NotFoundError(message, requestId);
      case 409:
        return new ConflictError(message, requestId, details);
      case 429:
        return new RateLimitError(message, requestId, retryAfter);
      case 500:
      case 502:
      case 503:
        return new ServerError(message, code, httpStatus, requestId, retryAfter);
      default:
        return new DataHubError(
          message,
          code,
          httpStatus,
          requestId,
          timestamp,
          details,
          retryAfter
        );
    }
  }

  // Fallback for unexpected error formats
  return null;
}

// ── Phase 118G.23: Domain-specific error classes ────────

export class BillingError extends DataHubError {
  constructor(m: string, code = 'BILLING_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class BillingValidationError extends BillingError {
  constructor(m: string, rid?: string) { super(m, 'BILLING_VALIDATION_ERROR', 400, rid); }
}
export class DowngradeLimitExceededError extends BillingError {
  constructor(m: string, rid?: string) { super(m, 'DOWNGRADE_LIMIT_EXCEEDED', 400, rid); }
}
export class TransformationError extends DataHubError {
  constructor(m: string, code = 'TRANSFORMATION_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class TransformationValidationError extends TransformationError {
  constructor(m: string, rid?: string) { super(m, 'TRANSFORMATION_VALIDATION_ERROR', 400, rid); }
}
export class ComplianceError extends DataHubError {
  constructor(m: string, code = 'COMPLIANCE_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class ComplianceValidationError extends ComplianceError {
  constructor(m: string, rid?: string) { super(m, 'COMPLIANCE_VALIDATION_ERROR', 400, rid); }
}
export class SemanticError extends DataHubError {
  constructor(m: string, code = 'SEMANTIC_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class SPARQLError extends SemanticError {
  constructor(m: string, rid?: string) { super(m, 'SPARQL_ERROR', 400, rid); }
}
export class SHACLValidationError extends SemanticError {
  constructor(m: string, rid?: string) { super(m, 'SHACL_VALIDATION_ERROR', 400, rid); }
}
export class WorkflowError extends DataHubError {
  constructor(m: string, code = 'WORKFLOW_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class DLQError extends DataHubError {
  constructor(m: string, code = 'DLQ_ERROR', s = 500, rid?: string) { super(m, code, s, rid); }
}
export class EntitlementRequiredError extends DataHubError {
  constructor(m = 'Entitlement required', rid?: string) { super(m, 'ENTITLEMENT_REQUIRED', 403, rid); }
}
export class CircuitBreakerOpenError extends ServerError {
  constructor(m = 'Circuit breaker open', rid?: string) { super(m, 'CIRCUIT_BREAKER_OPEN', 503, rid); }
}
export class ModelDeploymentError extends DataHubError {
  constructor(m: string, code = 'MODEL_DEPLOYMENT_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class MarketplaceError extends DataHubError {
  constructor(m: string, code = 'MARKETPLACE_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class MarketplaceValidationError extends MarketplaceError {
  constructor(m: string, rid?: string) { super(m, 'MARKETPLACE_VALIDATION_ERROR', 400, rid); }
}
export class BaaSError extends DataHubError {
  constructor(m: string, code = 'BAAS_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class BaaSValidationError extends BaaSError {
  constructor(m: string, rid?: string) { super(m, 'BAAS_VALIDATION_ERROR', 400, rid); }
}
export class ODHMLError extends DataHubError {
  constructor(m: string, code = 'ML_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class ODHMLValidationError extends ODHMLError {
  constructor(m: string, rid?: string) { super(m, 'ML_VALIDATION_ERROR', 400, rid); }
}
export class GovernanceError extends DataHubError {
  constructor(m: string, code = 'GOVERNANCE_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class MeshError extends DataHubError {
  constructor(m: string, code = 'MESH_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class VirtualizationError extends DataHubError {
  constructor(m: string, code = 'VIRTUALIZATION_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class WebhookError extends DataHubError {
  constructor(m: string, code = 'WEBHOOK_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class GDPRError extends DataHubError {
  constructor(m: string, code = 'GDPR_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class ScheduledIngestionError extends DataHubError {
  constructor(m: string, code = 'INGESTION_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class ScheduledExportError extends DataHubError {
  constructor(m: string, code = 'EXPORT_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class DQError extends DataHubError {
  constructor(m: string, code = 'DQ_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class SearchError extends DataHubError {
  constructor(m: string, code = 'SEARCH_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}
export class ObservabilityError extends DataHubError {
  constructor(m: string, code = 'OBSERVABILITY_ERROR', s = 400, rid?: string) { super(m, code, s, rid); }
}

