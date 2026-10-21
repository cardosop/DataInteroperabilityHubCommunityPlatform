/**
 * Error Tests
 */

import {
  DataHubError,
  ValidationError,
  UnauthorizedError,
  NotFoundError,
  RateLimitError,
  ServerError,
  parseError,
  parseRetryAfter,
} from '../errors';

describe('Error Classes', () => {
  describe('DataHubError', () => {
    it('should create error with all properties', () => {
      const error = new DataHubError(
        'Test error',
        'TEST_ERROR',
        400,
        'req-123',
        '2025-01-15T10:00:00Z',
        { field: 'value' }
      );

      expect(error.message).toBe('Test error');
      expect(error.code).toBe('TEST_ERROR');
      expect(error.httpStatus).toBe(400);
      expect(error.requestId).toBe('req-123');
      expect(error.timestamp).toBe('2025-01-15T10:00:00Z');
      expect(error.details).toEqual({ field: 'value' });
    });

    it('should convert to JSON', () => {
      const error = new DataHubError(
        'Test error',
        'TEST_ERROR',
        400,
        'req-123'
      );

      const json = error.toJSON();
      expect(json.error.code).toBe('TEST_ERROR');
      expect(json.error.message).toBe('Test error');
      expect(json.error.http_status).toBe(400);
      expect(json.error.request_id).toBe('req-123');
    });
  });

  describe('Specific Error Types', () => {
    it('should create ValidationError', () => {
      const error = new ValidationError('Invalid input', 'req-123', undefined, {
        field_errors: [],
      });

      expect(error).toBeInstanceOf(ValidationError);
      expect(error.httpStatus).toBe(400);
      expect(error.code).toBe('VALIDATION_ERROR');
    });

    it('should create UnauthorizedError', () => {
      const error = new UnauthorizedError('Auth required', 'req-123');

      expect(error).toBeInstanceOf(UnauthorizedError);
      expect(error.httpStatus).toBe(401);
      expect(error.code).toBe('AUTH_UNAUTHORIZED');
    });

    it('should create NotFoundError', () => {
      const error = new NotFoundError('Not found', 'req-123');

      expect(error).toBeInstanceOf(NotFoundError);
      expect(error.httpStatus).toBe(404);
      expect(error.code).toBe('NOT_FOUND');
    });

    it('should create RateLimitError with retryAfter', () => {
      const error = new RateLimitError('Rate limit exceeded', 'req-123', 60);

      expect(error).toBeInstanceOf(RateLimitError);
      expect(error.httpStatus).toBe(429);
      expect(error.retryAfter).toBe(60);
    });
  });

  describe('parseError', () => {
    it('should parse ValidationError', () => {
      const response = {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Invalid input',
          http_status: 400,
          request_id: 'req-123',
        },
      };

      const error = parseError(response);
      expect(error).toBeInstanceOf(ValidationError);
      expect(error!.httpStatus).toBe(400);
    });

    it('should parse UnauthorizedError', () => {
      const response = {
        error: {
          code: 'AUTH_UNAUTHORIZED',
          message: 'Auth required',
          http_status: 401,
        },
      };

      const error = parseError(response);
      expect(error).toBeInstanceOf(UnauthorizedError);
    });

    it('should parse ServerError for 5xx', () => {
      const response = {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Server error',
          http_status: 500,
        },
      };

      const error = parseError(response);
      expect(error!.httpStatus).toBe(500);
    });

    it('should read Retry-After from real response headers for 429 (W6.2)', () => {
      const response = {
        error: {
          code: 'RATE_LIMIT_EXCEEDED',
          message: 'Slow down',
          http_status: 429,
        },
      };

      const error = parseError(response, { 'retry-after': '120' });

      expect(error).toBeInstanceOf(RateLimitError);
      expect(error!.retryAfter).toBe(120);
    });

    it('should attach Retry-After to 503 ServerErrors too (W6.2)', () => {
      const response = {
        error: {
          code: 'SERVICE_UNAVAILABLE',
          message: 'Maintenance',
          http_status: 503,
        },
      };

      const error = parseError(response, { 'retry-after': '30' });

      expect(error).toBeInstanceOf(ServerError);
      expect(error!.retryAfter).toBe(30);
    });

    it('should use the envelope-less fallbackStatus when provided', () => {
      const response = {
        error: { code: 'NOT_FOUND', message: 'Missing' },
      };

      const error = parseError(response, {}, 404);

      expect(error).toBeInstanceOf(NotFoundError);
    });

    it('should return null for a non-envelope body (W6.2)', () => {
      expect(parseError({ detail: 'nope' })).toBeNull();
    });
  });

  describe('parseRetryAfter', () => {

    it('should parse delta-seconds', () => {
      expect(parseRetryAfter('120')).toBe(120);
      expect(parseRetryAfter('0')).toBe(0);
    });

    it('should parse HTTP-date values', () => {
      const now = Date.now();
      const inTwo = new Date(now + 2000).toUTCString();
      expect(parseRetryAfter(inTwo, now)).toBeGreaterThanOrEqual(1);
      expect(parseRetryAfter(inTwo, now)).toBeLessThanOrEqual(2);
    });

    it('should return undefined for absent or garbage values', () => {
      expect(parseRetryAfter(undefined)).toBeUndefined();
      expect(parseRetryAfter('')).toBeUndefined();
      expect(parseRetryAfter('soon-ish')).toBeUndefined();
    });
  });
});

