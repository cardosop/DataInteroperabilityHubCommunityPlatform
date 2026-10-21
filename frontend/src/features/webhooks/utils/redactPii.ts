/**
 * Phase 233.2 (REQ-WH-UI-004) — client-side PII redaction for the webhook
 * delivery payload viewer.
 *
 * The platform's primary defence is BACKEND redaction at write-time
 * (`hub.apps.audit.redaction`); this module provides the SECONDARY,
 * defence-in-depth client-side pass run on data already received from the
 * API. Two passes catch the failure mode where a backend code change
 * accidentally drops a redactor — the UI still masks the leak from the
 * operator viewing the payload.
 *
 * Patterns covered:
 *   - email addresses (RFC 5322 simplified)
 *   - phone numbers (E.164 + common North-American formats)
 *   - credit card numbers (13-19 digits, optionally separated by spaces or dashes)
 *
 * Patterns deliberately NOT covered here:
 *   - government IDs (country-specific; relies on the backend's pattern dictionary)
 *   - secrets / API keys (never appear in webhook payloads — they live in the
 *     X-Webhook-Signature header, not the body)
 *
 * The masking format preserves the SHAPE of the value so an operator can
 * recognise "this is an email" without seeing the email itself:
 *   alice@example.com  →  a***@e***le.com
 *   +1 415 555 1234   →  +***-***-***-1234
 *   4111-1111-1111-1111 → ****-****-****-1111
 */

const EMAIL_RE = /([a-zA-Z0-9_.+-])([a-zA-Z0-9_.+-]*?)@([a-zA-Z0-9-])([a-zA-Z0-9-]*?)(\.[a-zA-Z0-9.-]+)/g;

// Phone: international (+CC) or North-American 10-digit. Captures variations
// with spaces, dashes, parentheses. The trailing 4 digits are PRESERVED to
// keep the value recognisable as a phone number.
const PHONE_RE = /(\+?\d[\d\s\-().]{7,}\d)/g;

// Credit card: 13-19 digits with optional spaces / dashes between groups.
// Anchored to non-digit boundaries so we don't match arbitrary long numbers
// embedded in event ids.
const CC_RE = /(?<![0-9])(\d[\d\s-]{11,21}\d)(?![0-9])/g;

function maskEmail(_match: string, ...captures: string[]): string {
  // captures = [local0, localRest, domain0, domainRest, tld]
  const local0 = captures[0] ?? '';
  const domain0 = captures[2] ?? '';
  const domainRest = captures[3] ?? '';
  const tld = captures[4] ?? '';
  const lastTwoOfDomain =
    domainRest.length >= 2 ? domainRest.slice(-2) : domainRest;
  return `${local0}***@${domain0}***${lastTwoOfDomain}${tld}`;
}

function maskPhone(match: string): string {
  // Strip non-digits to find the last four — preserve original separators
  // would be nice but masking gives stronger guarantees.
  const digits = match.replace(/\D/g, '');
  if (digits.length < 7) {
    // Not actually a phone-shaped number; leave alone.
    return match;
  }
  const last4 = digits.slice(-4);
  return `+***-***-***-${last4}`;
}

function maskCreditCard(match: string): string {
  const digits = match.replace(/\D/g, '');
  if (digits.length < 13 || digits.length > 19) {
    return match;
  }
  // 233.2.R1 GAP-A — require AT LEAST ONE separator (space or dash) inside
  // the captured match to be treated as a credit card. A 14-digit raw
  // string without separators is more likely a user_id, order_id, or
  // other long opaque identifier than a CC; falling through here lets the
  // PHONE_RE pass mask it instead (still preserves the security
  // guarantee but produces a more accurate shape for the operator).
  // Real-world CCs are almost universally written with separators in
  // payload bodies (4111-1111-1111-1234 or 4111 1111 1111 1234) — the
  // separator-required heuristic preserves all true positives.
  if (!/[\s-]/.test(match)) {
    return match;
  }
  const last4 = digits.slice(-4);
  // Render as 4-4-4-4 for the common 16-digit case; for 13-15-19 lengths,
  // the leading masked group is short/long but the trailing four stays
  // consistent.
  return `****-****-****-${last4}`;
}

/**
 * Recursively walk a JSON-like value, masking PII in any string leaves.
 * Returns a NEW value tree — the input is not mutated. Cycles are not
 * tolerated (webhook payloads are pure JSON; cycles cannot exist).
 */
export function redactPiiInValue(value: unknown): unknown {
  if (typeof value === 'string') {
    return redactPiiInString(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactPiiInValue(item));
  }
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, v] of Object.entries(value as Record<string, unknown>)) {
      out[key] = redactPiiInValue(v);
    }
    return out;
  }
  return value;
}

/**
 * Mask PII in a single string. Order of passes matters: email FIRST so the
 * `@` doesn't get gobbled by the more aggressive phone matcher (which
 * tolerates separators `()` and `-`).
 */
export function redactPiiInString(input: string): string {
  let s = input;
  s = s.replace(EMAIL_RE, maskEmail);
  s = s.replace(CC_RE, maskCreditCard);
  s = s.replace(PHONE_RE, maskPhone);
  return s;
}

/**
 * Convenience: redact then JSON.stringify with pretty-printing for the
 * expanded panel. Returns a string ready for a `<pre>` tag.
 */
export function redactAndPrettyPrint(value: unknown): string {
  const redacted = redactPiiInValue(value);
  if (typeof redacted === 'string') {
    return redacted;
  }
  try {
    return JSON.stringify(redacted, null, 2);
  } catch {
    return String(redacted);
  }
}
