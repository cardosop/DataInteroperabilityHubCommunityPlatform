/**
 * Error Utils Tests
 * Tests for error normalization utility
 */

import { describe, expect, it } from 'vitest';
import type { ApiError } from '../types/api';
import { normalizeError } from './errorUtils';

describe('normalizeError', () => {
  it('should normalize ApiError correctly', () => {
    const apiError: ApiError = {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Invalid input',
        http_status: 400,
        request_id: 'req-123',
        timestamp: '2024-01-01T00:00:00Z',
        details: { field: 'email' },
      },
    };

    const normalized = normalizeError(apiError);

    expect(normalized.error.code).toBe('VALIDATION_ERROR');
    expect(normalized.error.message).toBe('Invalid input');
    expect(normalized.error.http_status).toBe(400);
    expect(normalized.error.request_id).toBe('req-123');
    expect(normalized.error.details).toEqual({ field: 'email' });
  });

  it('should normalize Error instance correctly', () => {
    const error = new Error('Something went wrong');
    error.name = 'CustomError';

    const normalized = normalizeError(error);

    expect(normalized.error.code).toBe('JAVASCRIPT_ERROR');
    expect(normalized.error.message).toBe('Something went wrong');
    expect(normalized.error.http_status).toBe(500);
    expect(normalized.error.details?.name).toBe('CustomError');
    expect(normalized.error.details?.stack).toBeDefined();
  });

  it('should normalize string error correctly', () => {
    const error = 'A string error occurred';

    const normalized = normalizeError(error);

    expect(normalized.error.code).toBe('STRING_ERROR');
    expect(normalized.error.message).toBe('A string error occurred');
    expect(normalized.error.http_status).toBe(500);
  });

  it('should normalize unknown error type correctly', () => {
    const error = { some: 'unknown', structure: 123 };

    const normalized = normalizeError(error);

    expect(normalized.error.code).toBe('UNKNOWN_ERROR');
    expect(normalized.error.message).toBe('An unexpected error occurred');
    expect(normalized.error.http_status).toBe(500);
    expect(normalized.error.details?.original).toBeDefined();
  });

  it('should preserve code and details from ApiError', () => {
    const apiError: ApiError = {
      error: {
        code: 'CUSTOM_CODE',
        message: 'Custom message',
        http_status: 422,
        request_id: 'req-456',
        timestamp: '2024-01-01T00:00:00Z',
        details: {
          custom_field: 'value',
          nested: { data: 123 },
        },
        field_errors: [{ field: 'email', message: 'Invalid email', code: 'INVALID_EMAIL' }],
      },
    };

    const normalized = normalizeError(apiError);

    expect(normalized.error.code).toBe('CUSTOM_CODE');
    expect(normalized.error.details).toEqual({
      custom_field: 'value',
      nested: { data: 123 },
    });
    expect(normalized.error.field_errors).toEqual([
      { field: 'email', message: 'Invalid email', code: 'INVALID_EMAIL' },
    ]);
  });

  it('should handle ApiError with missing optional fields', () => {
    const apiError: ApiError = {
      error: {
        code: 'MINIMAL_ERROR',
        message: 'Minimal error',
        http_status: 500,
        request_id: 'req-789',
        timestamp: '2024-01-01T00:00:00Z',
      },
    };

    const normalized = normalizeError(apiError);

    expect(normalized.error.code).toBe('MINIMAL_ERROR');
    expect(normalized.error.details).toBeUndefined();
    expect(normalized.error.field_errors).toBeUndefined();
  });

  it('should handle null/undefined gracefully', () => {
    const normalizedNull = normalizeError(null);
    expect(normalizedNull.error.code).toBe('UNKNOWN_ERROR');

    const normalizedUndefined = normalizeError(undefined);
    expect(normalizedUndefined.error.code).toBe('UNKNOWN_ERROR');
  });
});
