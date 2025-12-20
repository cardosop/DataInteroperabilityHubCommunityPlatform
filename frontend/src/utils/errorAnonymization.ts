/**
 * Error Anonymization Utilities
 *
 * Utilities for removing PII (Personally Identifiable Information) from errors
 * before sending to error tracking services.
 */

/**
 * Patterns for detecting PII
 */
const PII_PATTERNS = {
  // Email addresses
  email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
  // Phone numbers (various formats)
  phone: /\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b/g,
  // Credit card numbers
  creditCard: /\b(?:\d{4}[-\s]?){3}\d{4}\b/g,
  // SSN (US Social Security Numbers)
  ssn: /\b\d{3}-\d{2}-\d{4}\b/g,
  // IP addresses
  ipAddress: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,
  // API keys / tokens (common patterns)
  apiKey: /\b(?:api[_-]?key|token|secret|password|auth)[=:]\s*['"]?[A-Za-z0-9_-]{20,}['"]?/gi,
  // JWT tokens
  jwt: /\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g,
  // UUIDs (may contain user IDs)
  uuid: /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi,
} as const

/**
 * Fields that commonly contain PII and should be redacted
 */
const SENSITIVE_FIELDS = [
  'password',
  'password_confirmation',
  'current_password',
  'new_password',
  'token',
  'access_token',
  'refresh_token',
  'api_key',
  'apiKey',
  'secret',
  'secret_key',
  'authorization',
  'authorization_header',
  'auth',
  'credentials',
  'email',
  'email_address',
  'phone',
  'phone_number',
  'ssn',
  'social_security_number',
  'credit_card',
  'card_number',
  'cvv',
  'cvc',
  'billing_address',
  'shipping_address',
  'address',
  'full_name',
  'first_name',
  'last_name',
  'username',
  'user_id',
  'account_id',
  'session_id',
  'cookie',
  'cookies',
] as const

/**
 * Redact PII from a string
 *
 * @param text - Text to redact
 * @param replacement - Replacement string (default: '[REDACTED]')
 * @returns Redacted text
 */
export function redactPII(text: string, replacement: string = '[REDACTED]'): string {
  let redacted = text

  // Replace email addresses
  redacted = redacted.replace(PII_PATTERNS.email, replacement)
  // Replace phone numbers
  redacted = redacted.replace(PII_PATTERNS.phone, replacement)
  // Replace credit card numbers
  redacted = redacted.replace(PII_PATTERNS.creditCard, replacement)
  // Replace SSN
  redacted = redacted.replace(PII_PATTERNS.ssn, replacement)
  // Replace IP addresses
  redacted = redacted.replace(PII_PATTERNS.ipAddress, replacement)
  // Replace API keys
  redacted = redacted.replace(PII_PATTERNS.apiKey, replacement)
  // Replace JWT tokens
  redacted = redacted.replace(PII_PATTERNS.jwt, replacement)
  // Replace UUIDs (optional - may be too aggressive)
  // redacted = redacted.replace(PII_PATTERNS.uuid, replacement)

  return redacted
}

/**
 * Anonymize an object by removing or redacting sensitive fields
 *
 * @param obj - Object to anonymize
 * @param depth - Maximum depth for nested objects (default: 5)
 * @returns Anonymized object
 */
export function anonymizeObject(
  obj: any,
  depth: number = 5,
  currentDepth: number = 0
): any {
  if (currentDepth >= depth) {
    return '[MAX_DEPTH_REACHED]'
  }

  if (obj === null || obj === undefined) {
    return obj
  }

  // Handle primitives
  if (typeof obj !== 'object') {
    if (typeof obj === 'string') {
      return redactPII(obj)
    }
    return obj
  }

  // Handle arrays
  if (Array.isArray(obj)) {
    return obj.map((item) => anonymizeObject(item, depth, currentDepth + 1))
  }

  // Handle objects
  const anonymized: Record<string, any> = {}

  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase()

    // Check if field is sensitive
    if (SENSITIVE_FIELDS.some((field) => lowerKey.includes(field))) {
      anonymized[key] = '[REDACTED]'
    } else if (typeof value === 'string') {
      // Redact PII from string values
      anonymized[key] = redactPII(value)
    } else if (typeof value === 'object' && value !== null) {
      // Recursively anonymize nested objects
      anonymized[key] = anonymizeObject(value, depth, currentDepth + 1)
    } else {
      anonymized[key] = value
    }
  }

  return anonymized
}

/**
 * Anonymize error object for logging
 *
 * @param error - Error to anonymize
 * @returns Anonymized error data
 */
export function anonymizeError(error: unknown): {
  message: string
  name: string
  stack?: string
  [key: string]: any
} {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: redactPII(error.message),
      stack: error.stack ? redactPII(error.stack) : undefined,
      ...anonymizeObject(Object.assign({}, error)),
    }
  }

  if (typeof error === 'object' && error !== null) {
    return anonymizeObject(error) as any
  }

  return {
    message: redactPII(String(error)),
    name: 'Unknown',
  }
}

