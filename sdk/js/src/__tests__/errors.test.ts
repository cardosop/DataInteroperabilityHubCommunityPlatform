/**
 * Error Tests
 */

import {
  DataHubError,
  ValidationError,
  UnauthorizedError,
  NotFoundError,
  RateLimitError,
  parseError,
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
      const error = new ValidationError('Invalid input', 'req-123', {
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
      expect(error.httpStatus).toBe(400);
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
      expect(error.httpStatus).toBe(500);
    });
  });
});

