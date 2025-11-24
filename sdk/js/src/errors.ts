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

  constructor(
    message: string,
    code: string,
    httpStatus: number,
    requestId?: string,
    timestamp?: string,
    details?: ErrorDetails
  ) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.httpStatus = httpStatus;
    this.requestId = requestId;
    this.timestamp = timestamp;
    this.details = details;
    
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
  constructor(message: string, requestId?: string, details?: ErrorDetails) {
    super(message, 'VALIDATION_ERROR', 400, requestId, undefined, details);
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
  public readonly retryAfter?: number;

  constructor(
    message: string,
    requestId?: string,
    retryAfter?: number
  ) {
    super(message, 'RATE_LIMIT_EXCEEDED', 429, requestId);
    this.retryAfter = retryAfter;
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
    requestId?: string
  ) {
    super(message, code, httpStatus, requestId);
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
 * Parse API error response and return appropriate error class
 */
export function parseError(response: any): DataHubError {
  if (response?.error) {
    const error = response.error;
    const code = error.code || 'UNKNOWN_ERROR';
    const httpStatus = error.http_status || 500;
    const message = error.message || 'An error occurred';
    const requestId = error.request_id;
    const timestamp = error.timestamp;
    const details = error.details;

    // Map error codes to specific error classes
    switch (httpStatus) {
      case 400:
        return new ValidationError(message, requestId, details);
      case 401:
        return new UnauthorizedError(message, requestId);
      case 403:
        return new ForbiddenError(message, requestId);
      case 404:
        return new NotFoundError(message, requestId);
      case 409:
        return new ConflictError(message, requestId, details);
      case 429:
        const retryAfter = response.headers?.['retry-after']
          ? parseInt(response.headers['retry-after'], 10)
          : undefined;
        return new RateLimitError(message, requestId, retryAfter);
      case 500:
      case 502:
      case 503:
        return new ServerError(message, code, httpStatus, requestId);
      default:
        return new DataHubError(
          message,
          code,
          httpStatus,
          requestId,
          timestamp,
          details
        );
    }
  }

  // Fallback for unexpected error formats
  return new ServerError('Unexpected error format', 'UNKNOWN_ERROR', 500);
}

