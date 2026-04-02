/**
 * Feature flags unit tests
 */

import { describe, expect, it } from 'vitest';
import {
  FEATURE_BREADCRUMBS_ENABLED,
  FEATURE_RESOURCE_PICKERS_ENABLED,
  parseBool,
} from '../featureFlags';

describe('parseBool', () => {
  it('returns true for undefined', () => {
    expect(parseBool(undefined)).toBe(true);
  });

  it('returns true for empty string', () => {
    expect(parseBool('')).toBe(true);
  });

  it('returns true for "true" (case-insensitive)', () => {
    expect(parseBool('true')).toBe(true);
    expect(parseBool('True')).toBe(true);
    expect(parseBool('TRUE')).toBe(true);
  });

  it('returns true for "1"', () => {
    expect(parseBool('1')).toBe(true);
  });

  it('returns true for trimmed " true "', () => {
    expect(parseBool('  true  ')).toBe(true);
  });

  it('returns false for "false" (case-insensitive)', () => {
    expect(parseBool('false')).toBe(false);
    expect(parseBool('False')).toBe(false);
    expect(parseBool('FALSE')).toBe(false);
  });

  it('returns false for "0"', () => {
    expect(parseBool('0')).toBe(false);
  });

  it('returns false for unknown values', () => {
    expect(parseBool('yes')).toBe(false);
    expect(parseBool('no')).toBe(false);
    expect(parseBool('enabled')).toBe(false);
  });
});

describe('feature flags', () => {
  it('exports boolean FEATURE_BREADCRUMBS_ENABLED', () => {
    expect(typeof FEATURE_BREADCRUMBS_ENABLED).toBe('boolean');
  });

  it('exports boolean FEATURE_RESOURCE_PICKERS_ENABLED', () => {
    expect(typeof FEATURE_RESOURCE_PICKERS_ENABLED).toBe('boolean');
  });
});
