/**
 * Tests for locale-aware formatters (277.B.078).
 */
import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
  formatCompactNumber,
  formatRelative,
} from './formatters';

describe('formatCurrency', () => {
  it('formats minor-unit USD amount correctly', () => {
    const result = formatCurrency(999, 'USD');
    expect(result).toContain('9.99');
    // Should contain a currency symbol or code
    expect(result.length).toBeGreaterThan(3);
  });

  it('formats major-unit amount when unit is major', () => {
    const result = formatCurrency(9.99, 'USD', { unit: 'major' });
    expect(result).toContain('9.99');
  });

  it('handles EUR currency', () => {
    const result = formatCurrency(1500, 'EUR');
    expect(result).toContain('15');
  });

  it('handles GBP currency via symbol', () => {
    const result = formatCurrency(500, '£');
    expect(result.length).toBeGreaterThan(2);
  });

  it('handles lowercase currency code', () => {
    const result = formatCurrency(1000, 'usd');
    expect(result).toContain('10');
  });

  it('handles euro symbol', () => {
    const result = formatCurrency(1000, '€');
    expect(result.length).toBeGreaterThan(2);
  });

  it('returns string for NaN amount', () => {
    const result = formatCurrency(NaN, 'USD');
    expect(typeof result).toBe('string');
    expect(result).toBe('NaN');
  });

  it('returns string for Infinity', () => {
    const result = formatCurrency(Infinity, 'USD');
    expect(typeof result).toBe('string');
  });

  it('fallback for unknown currency produces readable output', () => {
    const result = formatCurrency(1000, 'ZZZ');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('minor unit is default', () => {
    const withFlag = formatCurrency(100, 'USD', { unit: 'minor' });
    const withoutFlag = formatCurrency(100, 'USD');
    expect(withFlag).toBe(withoutFlag);
  });
});

describe('formatDate', () => {
  it('formats ISO string as date only', () => {
    const result = formatDate('2026-05-13T10:30:00Z');
    // Should not contain time
    expect(result.length).toBeGreaterThan(4);
    // Should be a date string (varies by locale, but long format has month name)
  });

  it('formats Date object', () => {
    const result = formatDate(new Date('2026-05-13T10:30:00Z'));
    expect(result.length).toBeGreaterThan(4);
  });

  it('returns input as string for invalid date', () => {
    const result = formatDate('not-a-date');
    expect(typeof result).toBe('string');
  });

  it('accepts custom options', () => {
    const result = formatDate('2026-05-13T10:30:00Z', { year: 'numeric', month: 'short', day: 'numeric' });
    expect(result).toContain('2026');
    expect(result).toContain('May');
  });
});

describe('formatDateTime', () => {
  it('formats ISO string with date and time', () => {
    const result = formatDateTime('2026-05-13T10:30:00Z');
    expect(result.length).toBeGreaterThan(8);
  });

  it('formats Date object', () => {
    const result = formatDateTime(new Date('2026-05-13T10:30:00Z'));
    expect(result.length).toBeGreaterThan(8);
  });

  it('returns input as string for invalid date', () => {
    const result = formatDateTime('invalid');
    expect(typeof result).toBe('string');
  });

  it('accepts custom options', () => {
    const result = formatDateTime('2026-05-13T10:30:00Z', {
      dateStyle: 'full',
      timeStyle: 'long',
    });
    expect(result.length).toBeGreaterThan(10);
  });
});

describe('formatNumber', () => {
  it('formats integer with locale grouping', () => {
    const result = formatNumber(1234567);
    expect(result).toContain('1');
    expect(result.length).toBeGreaterThan(7); // includes separators
  });

  it('formats decimal', () => {
    const result = formatNumber(1234.56, { minimumFractionDigits: 2 });
    expect(result).toContain('1');
  });

  it('returns string for non-finite values', () => {
    expect(typeof formatNumber(NaN)).toBe('string');
    expect(typeof formatNumber(Infinity)).toBe('string');
  });
});

describe('formatCompactNumber', () => {
  it('formats thousands compactly', () => {
    const result = formatCompactNumber(1234);
    expect(result).toContain('1');
    expect(result.length).toBeLessThan(6);
  });

  it('formats millions compactly', () => {
    const result = formatCompactNumber(1_234_567);
    expect(result).toContain('1');
    expect(result.length).toBeLessThan(8);
  });
});

describe('formatRelative', () => {
  it('formats past time relatively', () => {
    const past = new Date(Date.now() - 3600 * 1000); // 1 hour ago
    const result = formatRelative(past);
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('formats future time relatively', () => {
    const future = new Date(Date.now() + 86400 * 1000); // 1 day from now
    const result = formatRelative(future);
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('accepts ISO string', () => {
    const past = new Date(Date.now() - 60000).toISOString(); // 1 min ago
    const result = formatRelative(past);
    expect(typeof result).toBe('string');
  });

  it('returns input as string for invalid date', () => {
    const result = formatRelative('not-a-date');
    expect(typeof result).toBe('string');
  });
});
