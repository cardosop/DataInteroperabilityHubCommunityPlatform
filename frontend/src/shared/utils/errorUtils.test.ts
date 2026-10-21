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

/* -------------------------------------------------------------------------
 * Phase 227 Wave 1 (227.L5.9) — getErrorRemediation tests
 * ------------------------------------------------------------------------- */

import { getErrorRemediation, KnownErrorCode } from './errorUtils';

describe('getErrorRemediation', () => {
  it('returns null for unknown codes', () => {
    expect(getErrorRemediation('NOT_A_REAL_CODE')).toBeNull();
    expect(getErrorRemediation(null)).toBeNull();
    expect(getErrorRemediation(undefined)).toBeNull();
    expect(getErrorRemediation('')).toBeNull();
  });

  it('returns subcode-specific copy for STRUCTURELESS_CONTRACT', () => {
    const odpsNoPorts = getErrorRemediation(
      KnownErrorCode.STRUCTURELESS_CONTRACT,
      'STRUCTURELESS_ODPS_NO_PORTS',
    );
    expect(odpsNoPorts).not.toBeNull();
    expect(odpsNoPorts!.title).toContain('models or schema fields');
    expect(odpsNoPorts!.details).toContain('outputPort');

    const odcsNoSchema = getErrorRemediation(
      KnownErrorCode.STRUCTURELESS_CONTRACT,
      'STRUCTURELESS_ODCS_NO_SCHEMA',
    );
    expect(odcsNoSchema!.details).toContain('Schema editor');

    const cyclic = getErrorRemediation(
      KnownErrorCode.STRUCTURELESS_CONTRACT,
      'STRUCTURELESS_CYCLIC_PORTS',
    );
    expect(cyclic!.details).toContain('cycle');
  });

  it('falls back to generic copy when subcode is unknown', () => {
    const r = getErrorRemediation(KnownErrorCode.STRUCTURELESS_CONTRACT, 'NOT_A_REAL_SUBCODE');
    expect(r).not.toBeNull();
    expect(r!.details).toContain('no resolvable structure');
  });

  it('exposes remediation_url as ctaUrl when provided', () => {
    const url = 'https://example.com/contracts/abc/edit?tab=schema';
    const r = getErrorRemediation(
      KnownErrorCode.STRUCTURELESS_CONTRACT,
      'STRUCTURELESS_ODCS_NO_SCHEMA',
      { remediation_url: url },
    );
    expect(r!.ctaUrl).toBe(url);
    expect(r!.ctaLabel).toContain('Schema editor');
  });

  it('omits ctaUrl/Label when no remediation_url is provided', () => {
    const r = getErrorRemediation(
      KnownErrorCode.STRUCTURELESS_CONTRACT,
      'STRUCTURELESS_ODCS_NO_SCHEMA',
    );
    expect(r!.ctaUrl).toBeUndefined();
    expect(r!.ctaLabel).toBeUndefined();
  });

  it('returns specific copy for PRECONDITION_FAILED', () => {
    const r = getErrorRemediation(KnownErrorCode.PRECONDITION_FAILED);
    expect(r).not.toBeNull();
    expect(r!.title).toContain('changed since you opened');
  });

  it('returns specific copy for SCHEMA_TOO_DEEP', () => {
    const r = getErrorRemediation(KnownErrorCode.SCHEMA_TOO_DEEP);
    expect(r).not.toBeNull();
    expect(r!.details).toContain('20');
  });

  it('returns generic copy for VALIDATION_ERROR / NORMALIZATION_FAILED', () => {
    expect(getErrorRemediation(KnownErrorCode.VALIDATION_ERROR)).not.toBeNull();
    expect(getErrorRemediation(KnownErrorCode.NORMALIZATION_FAILED)).not.toBeNull();
  });

  it('is case-insensitive on the code argument', () => {
    expect(getErrorRemediation('structureless_contract')).not.toBeNull();
    expect(getErrorRemediation('Structureless_Contract')).not.toBeNull();
  });
});
