/**
 * Phase 233.2 — redactPii unit tests.
 *
 * Pins REQ-WH-UI-004's "DOM does not contain the original PII substring"
 * contract by feeding fixtures with email / phone / credit-card values and
 * asserting the redactor's output does not contain the input.
 */
import { describe, expect, it } from 'vitest';
import {
  redactAndPrettyPrint,
  redactPiiInString,
  redactPiiInValue,
} from './redactPii';

describe('redactPiiInString', () => {
  it('masks email addresses preserving shape', () => {
    const out = redactPiiInString('alice.smith@example.com');
    expect(out).not.toContain('alice.smith');
    expect(out).not.toContain('exampl');
    expect(out).toContain('@');
    expect(out).toContain('.com');
  });

  it('masks credit card numbers preserving last 4', () => {
    const out = redactPiiInString('Card: 4111-1111-1111-1234');
    expect(out).not.toContain('4111-1111-1111');
    expect(out).toContain('1234');
  });

  it('masks phone numbers preserving last 4', () => {
    const out = redactPiiInString('+1 415 555 6789');
    expect(out).not.toContain('415 555');
    expect(out).toContain('6789');
  });

  it('leaves non-PII strings unchanged', () => {
    const out = redactPiiInString('order-id-abc123');
    expect(out).toBe('order-id-abc123');
  });

  it('redacts multiple emails in the same string', () => {
    const out = redactPiiInString('to: a@b.com, cc: c@d.com');
    expect(out).not.toContain('a@b.com');
    expect(out).not.toContain('c@d.com');
  });

  it('does not mask long pure-digit strings as credit cards (233.2.R1 GAP-A)', () => {
    // A 16-digit pure-digit identifier without separators is more likely
    // an order_id / user_id than a credit card. The CC matcher now
    // requires at least one separator inside the captured match before
    // masking — otherwise it falls through to the phone matcher (which
    // still masks it, but with phone shape rather than CC shape, giving
    // operators a more accurate picture). The security guarantee — the
    // raw digits are not visible verbatim — holds either way.
    const orderIdLike = 'order_id=1234567890123456';
    const out = redactPiiInString(orderIdLike);
    // Either the CC matcher leaves it alone and phone catches it, OR
    // the result is the same as the input. What MUST hold: the raw
    // 16-digit substring is not visible verbatim AND the output does
    // not contain the credit-card mask shape "****-****-****-".
    expect(out).not.toContain('1234567890123456');
    expect(out).not.toContain('****-****-****-');
  });
});

describe('redactPiiInValue', () => {
  it('walks nested objects and arrays', () => {
    const input = {
      user: {
        email: 'leak@example.com',
        addresses: [{ phone: '+1 415 555 1234' }],
      },
      meta: ['ok', 'card 4111111111111234'],
    };
    const out = redactPiiInValue(input) as typeof input;
    expect(JSON.stringify(out)).not.toContain('leak@example.com');
    expect(JSON.stringify(out)).not.toContain('415 555 1234');
    expect(JSON.stringify(out)).not.toContain('4111111111111234');
  });

  it('returns the same shape for non-string leaves', () => {
    const input = { count: 42, ok: true, tags: ['a', 'b'] };
    const out = redactPiiInValue(input) as typeof input;
    expect(out.count).toBe(42);
    expect(out.ok).toBe(true);
    expect(out.tags).toEqual(['a', 'b']);
  });

  it('does not mutate the input', () => {
    const input = { email: 'leak@example.com' };
    redactPiiInValue(input);
    expect(input.email).toBe('leak@example.com');
  });
});

describe('redactAndPrettyPrint', () => {
  it('returns a JSON-pretty-printed string for object inputs', () => {
    const out = redactAndPrettyPrint({ a: 1, email: 'leak@example.com' });
    expect(out).toContain('"a": 1');
    expect(out).not.toContain('leak@example.com');
  });

  it('returns redacted string for string inputs without quoting', () => {
    const out = redactAndPrettyPrint('hello leak@example.com');
    expect(out).toContain('hello');
    expect(out).not.toContain('leak@example.com');
  });
});
