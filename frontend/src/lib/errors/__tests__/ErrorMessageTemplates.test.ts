/**
 * ErrorMessageTemplates Tests
 *
 * Comprehensive tests for error message templates covering:
 * - Template retrieval
 * - User-friendly messages
 * - Suggested actions
 * - Help links
 * - Next steps
 * - No technical jargon
 */

import { describe, it, expect } from 'vitest'
import {
  ERROR_MESSAGE_TEMPLATES,
  getErrorMessageTemplate,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  getSuggestedActions,
  getHelpLinks,
  getNextSteps,
  isRecoverableError,
} from '../ErrorMessageTemplates'
import { ApiError, NetworkError } from '@/lib/api/errors'
import { FetchError } from '@/lib/api/fetch'

describe('ErrorMessageTemplates', () => {
  describe('Template Structure', () => {
    it('should have all required fields in templates', () => {
      Object.values(ERROR_MESSAGE_TEMPLATES).forEach((template) => {
        expect(template).toHaveProperty('code')
        expect(template).toHaveProperty('title')
        expect(template).toHaveProperty('message')
        expect(template).toHaveProperty('severity')
        expect(template).toHaveProperty('recoverable')
        expect(typeof template.title).toBe('string')
        expect(typeof template.message).toBe('string')
        expect(['error', 'warning', 'info']).toContain(template.severity)
        expect(typeof template.recoverable).toBe('boolean')
      })
    })

    it('should have user-friendly titles (no technical jargon)', () => {
      Object.values(ERROR_MESSAGE_TEMPLATES).forEach((template) => {
        // Should not contain technical terms
        expect(template.title.toLowerCase()).not.toContain('http')
        expect(template.title.toLowerCase()).not.toContain('status code')
        expect(template.title.toLowerCase()).not.toContain('500')
        expect(template.title.toLowerCase()).not.toContain('404')
        expect(template.title.toLowerCase()).not.toContain('exception')
        expect(template.title.toLowerCase()).not.toContain('error code')
      })
    })

    it('should have user-friendly messages (no technical jargon)', () => {
      Object.values(ERROR_MESSAGE_TEMPLATES).forEach((template) => {
        // Should not contain technical terms
        expect(template.message.toLowerCase()).not.toContain('http')
        expect(template.message.toLowerCase()).not.toContain('status code')
        expect(template.message.toLowerCase()).not.toContain('exception')
        expect(template.message.toLowerCase()).not.toContain('stack trace')
        expect(template.message.toLowerCase()).not.toContain('api error')
      })
    })

    it('should provide clear next steps', () => {
      Object.values(ERROR_MESSAGE_TEMPLATES).forEach((template) => {
        if (template.nextSteps) {
          expect(template.nextSteps.length).toBeGreaterThan(0)
          template.nextSteps.forEach((step) => {
            expect(typeof step).toBe('string')
            expect(step.length).toBeGreaterThan(0)
          })
        }
      })
    })
  })

  describe('getErrorMessageTemplate', () => {
    it('should return template for API error with code', () => {
      const axiosError = {
        response: { status: 404 },
      } as FetchError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)
      const template = getErrorMessageTemplate(apiError)

      expect(template.code).toBe('NOT_FOUND')
      expect(template.title).toBeTruthy()
      expect(template.message).toBeTruthy()
    })

    it('should return template for API error with HTTP status', () => {
      const axiosError = {
        response: { status: 500 },
      } as FetchError

      const apiError = new ApiError('Server error', 'HTTP_500', 500, axiosError)
      const template = getErrorMessageTemplate(apiError)

      expect(template.code).toBe('INTERNAL_SERVER_ERROR')
    })

    it('should return template for network error', () => {
      const fetchError = {} as FetchError
      const networkError = new NetworkError('Network error', axiosError)

      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        configurable: true,
        value: false,
      })

      const template = getErrorMessageTemplate(networkError)

      expect(template.code).toBe('OFFLINE')
    })

    it('should return template for generic Error', () => {
      const error = new Error('Network connection failed')
      const template = getErrorMessageTemplate(error)

      expect(template.code).toBe('NETWORK_ERROR')
    })

    it('should return unknown error template for unrecognized errors', () => {
      const unknownError = { someProperty: 'value' }
      const template = getErrorMessageTemplate(unknownError)

      expect(template.code).toBe('UNKNOWN_ERROR')
    })
  })

  describe('Helper Functions', () => {
    it('should get user-friendly error message', () => {
      const axiosError = {
        response: { status: 404 },
      } as FetchError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)
      const message = getUserFriendlyErrorMessage(apiError)

      expect(message).toBeTruthy()
      expect(typeof message).toBe('string')
      expect(message.toLowerCase()).not.toContain('404')
      expect(message.toLowerCase()).not.toContain('not found')
    })

    it('should get error title', () => {
      const axiosError = {
        response: { status: 401 },
      } as FetchError

      const apiError = new ApiError('Unauthorized', 'UNAUTHORIZED', 401, axiosError)
      const title = getErrorTitle(apiError)

      expect(title).toBeTruthy()
      expect(typeof title).toBe('string')
    })

    it('should get suggested actions', () => {
      const axiosError = {
        response: { status: 403 },
      } as FetchError

      const apiError = new ApiError('Forbidden', 'FORBIDDEN', 403, axiosError)
      const actions = getSuggestedActions(apiError)

      expect(Array.isArray(actions)).toBe(true)
      if (actions.length > 0) {
        actions.forEach((action) => {
          expect(action).toHaveProperty('label')
          expect(action).toHaveProperty('onClick')
          expect(typeof action.label).toBe('string')
          expect(typeof action.onClick).toBe('function')
        })
      }
    })

    it('should get help links', () => {
      const axiosError = {
        response: { status: 500 },
      } as FetchError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)
      const links = getHelpLinks(apiError)

      expect(Array.isArray(links)).toBe(true)
      if (links.length > 0) {
        links.forEach((link) => {
          expect(link).toHaveProperty('label')
          expect(link).toHaveProperty('url')
          expect(typeof link.label).toBe('string')
          expect(typeof link.url).toBe('string')
        })
      }
    })

    it('should get next steps', () => {
      const axiosError = {
        response: { status: 400 },
      } as FetchError

      const apiError = new ApiError('Validation error', 'VALIDATION_ERROR', 400, axiosError)
      const steps = getNextSteps(apiError)

      expect(Array.isArray(steps)).toBe(true)
      expect(steps.length).toBeGreaterThan(0)
      steps.forEach((step) => {
        expect(typeof step).toBe('string')
        expect(step.length).toBeGreaterThan(0)
      })
    })

    it('should check if error is recoverable', () => {
      const axiosError = {
        response: { status: 500 },
      } as FetchError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)
      const recoverable = isRecoverableError(apiError)

      expect(typeof recoverable).toBe('boolean')
      expect(recoverable).toBe(true) // Server errors are recoverable
    })
  })

  describe('Message Quality', () => {
    it('should have actionable messages', () => {
      Object.values(ERROR_MESSAGE_TEMPLATES).forEach((template) => {
        // Messages should suggest what user can do
        const hasActionWords =
          template.message.toLowerCase().includes('try') ||
          template.message.toLowerCase().includes('check') ||
          template.message.toLowerCase().includes('contact') ||
          template.message.toLowerCase().includes('please') ||
          template.suggestedActions?.length ||
          template.nextSteps?.length

        expect(hasActionWords).toBe(true)
      })
    })

    it('should have contextual messages', () => {
      Object.values(ERROR_MESSAGE_TEMPLATES).forEach((template) => {
        // Messages should explain what happened
        expect(template.message.length).toBeGreaterThan(20) // Not too short
        expect(template.message).not.toBe('Error') // Not too generic
      })
    })
  })
})

