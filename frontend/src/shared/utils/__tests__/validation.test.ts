/**
 * Validation Utilities Tests
 */

import { describe, expect, it } from 'vitest';
import { isValidUUID } from '../validation';

describe('isValidUUID', () => {
  it('returns true for valid UUID v4', () => {
    expect(isValidUUID('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
    expect(isValidUUID('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11')).toBe(true);
    expect(isValidUUID('FFFFFFFF-FFFF-4FFF-8FFF-FFFFFFFFFFFF')).toBe(true);
  });

  it('returns false for invalid UUID format', () => {
    expect(isValidUUID('not-a-uuid')).toBe(false);
    expect(isValidUUID('550e8400-e29b-41d4-a716')).toBe(false);
    expect(isValidUUID('550e8400-e29b-41d4-a716-446655440000-extra')).toBe(false);
    expect(isValidUUID('550e8400e29b41d4a716446655440000')).toBe(false);
  });

  it('returns false for null and undefined', () => {
    expect(isValidUUID(null)).toBe(false);
    expect(isValidUUID(undefined)).toBe(false);
  });

  it('returns false for empty or whitespace-only string', () => {
    expect(isValidUUID('')).toBe(false);
    expect(isValidUUID('   ')).toBe(false);
  });

  it('trims whitespace before validating', () => {
    expect(isValidUUID('  550e8400-e29b-41d4-a716-446655440000  ')).toBe(true);
  });
});
