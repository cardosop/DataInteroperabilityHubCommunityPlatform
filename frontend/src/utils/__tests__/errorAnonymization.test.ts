/**
 * Error Anonymization Utilities Tests
 *
 * Comprehensive tests for error anonymization utilities covering:
 * - PII detection and redaction
 * - Object anonymization
 * - Error anonymization
 */

import { describe, it, expect } from 'vitest'
import {
  redactPII,
  anonymizeObject,
  anonymizeError,
} from '../errorAnonymization'

describe('errorAnonymization utilities', () => {
  describe('redactPII', () => {
    it('should redact email addresses', () => {
      const text = 'Contact user@example.com for support'
      const result = redactPII(text)

      expect(result).not.toContain('user@example.com')
      expect(result).toContain('[REDACTED]')
    })

    it('should redact phone numbers', () => {
      const text = 'Call us at 555-123-4567'
      const result = redactPII(text)

      expect(result).not.toContain('555-123-4567')
      expect(result).toContain('[REDACTED]')
    })

    it('should redact credit card numbers', () => {
      const text = 'Card: 1234-5678-9012-3456'
      const result = redactPII(text)

      expect(result).not.toContain('1234-5678-9012-3456')
      expect(result).toContain('[REDACTED]')
    })

    it('should redact SSN', () => {
      const text = 'SSN: 123-45-6789'
      const result = redactPII(text)

      expect(result).not.toContain('123-45-6789')
      expect(result).toContain('[REDACTED]')
    })

    it('should redact API keys', () => {
      const text = 'api_key=abc123def456ghi789'
      const result = redactPII(text)

      expect(result).not.toContain('abc123def456ghi789')
      expect(result).toContain('[REDACTED]')
    })

    it('should redact JWT tokens', () => {
      const text = 'Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
      const result = redactPII(text)

      expect(result).not.toContain('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9')
      expect(result).toContain('[REDACTED]')
    })

    it('should use custom replacement', () => {
      const text = 'Email: user@example.com'
      const result = redactPII(text, '***')

      expect(result).toContain('***')
      expect(result).not.toContain('user@example.com')
    })
  })

  describe('anonymizeObject', () => {
    it('should anonymize sensitive fields', () => {
      const obj = {
        email: 'user@example.com',
        password: 'secret123',
        name: 'John Doe',
      }

      const result = anonymizeObject(obj)

      expect(result.email).toBe('[REDACTED]')
      expect(result.password).toBe('[REDACTED]')
      expect(result.name).not.toBe('[REDACTED]') // Name is not in sensitive fields list
    })

    it('should anonymize nested objects', () => {
      const obj = {
        user: {
          email: 'user@example.com',
          profile: {
            phone: '555-1234',
          },
        },
      }

      const result = anonymizeObject(obj)

      expect(result.user.email).toBe('[REDACTED]')
      expect(result.user.profile.phone).toBe('[REDACTED]')
    })

    it('should anonymize arrays', () => {
      const obj = {
        users: [
          { email: 'user1@example.com' },
          { email: 'user2@example.com' },
        ],
      }

      const result = anonymizeObject(obj)

      expect(result.users[0].email).toBe('[REDACTED]')
      expect(result.users[1].email).toBe('[REDACTED]')
    })

    it('should respect depth limit', () => {
      const obj = {
        level1: {
          level2: {
            level3: {
              level4: {
                level5: {
                  level6: 'deep',
                },
              },
            },
          },
        },
      }

      const result = anonymizeObject(obj, 3)

      expect(result.level1.level2).toBeDefined()
      // Beyond depth limit should be replaced
      expect(result.level1.level2.level3).toBe('[MAX_DEPTH_REACHED]')
    })
  })

  describe('anonymizeError', () => {
    it('should anonymize Error object', () => {
      const error = new Error('User email: user@example.com')
      const result = anonymizeError(error)

      expect(result.message).not.toContain('user@example.com')
      expect(result.message).toContain('[REDACTED]')
      expect(result.name).toBe('Error')
    })

    it('should anonymize error stack trace', () => {
      const error = new Error('Test error')
      error.stack = 'Error: Test error\n    at user@example.com'
      const result = anonymizeError(error)

      expect(result.stack).not.toContain('user@example.com')
      expect(result.stack).toContain('[REDACTED]')
    })

    it('should handle non-Error objects', () => {
      const error = { message: 'Error with user@example.com' }
      const result = anonymizeError(error)

      expect(result.message).not.toContain('user@example.com')
      expect(result.message).toContain('[REDACTED]')
    })

    it('should handle primitive errors', () => {
      const error = 'Error: user@example.com'
      const result = anonymizeError(error)

      expect(result.message).not.toContain('user@example.com')
      expect(result.message).toContain('[REDACTED]')
    })
  })
})

