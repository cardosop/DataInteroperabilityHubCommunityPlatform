/**
 * Safe Logger Utility
 * Prevents secrets from leaking to console logs
 */

const SENSITIVE_PATTERNS = [
  /password/i,
  /token/i,
  /secret/i,
  /api[_-]?key/i,
  /authorization/i,
  /bearer/i,
  /access[_-]?token/i,
  /refresh[_-]?token/i,
  /credential/i,
  /private[_-]?key/i,
];

/**
 * Sanitize object to remove sensitive data
 */
function sanitizeValue(value: unknown): unknown {
  if (value === null || value === undefined) {
    return value;
  }

  if (typeof value === 'string') {
    // Check if string contains sensitive patterns
    for (const pattern of SENSITIVE_PATTERNS) {
      if (pattern.test(value)) {
        return '[REDACTED]';
      }
    }
    return value;
  }

  if (typeof value === 'object') {
    if (Array.isArray(value)) {
      return value.map(sanitizeValue);
    }

    const sanitized: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
      // Check if key contains sensitive patterns
      let shouldRedact = false;
      for (const pattern of SENSITIVE_PATTERNS) {
        if (pattern.test(key)) {
          shouldRedact = true;
          break;
        }
      }

      if (shouldRedact) {
        sanitized[key] = '[REDACTED]';
      } else {
        sanitized[key] = sanitizeValue(val);
      }
    }
    return sanitized;
  }

  return value;
}

/**
 * Safe logger that sanitizes sensitive data
 */
export const safeLogger = {
  log: (...args: unknown[]) => {
    if (import.meta.env.DEV) {
      console.log(...args.map(sanitizeValue));
    }
  },
  error: (...args: unknown[]) => {
    console.error(...args.map(sanitizeValue));
  },
  warn: (...args: unknown[]) => {
    console.warn(...args.map(sanitizeValue));
  },
  debug: (...args: unknown[]) => {
    if (import.meta.env.DEV) {
      console.debug(...args.map(sanitizeValue));
    }
  },
  info: (...args: unknown[]) => {
    if (import.meta.env.DEV) {
      console.info(...args.map(sanitizeValue));
    }
  },
};
