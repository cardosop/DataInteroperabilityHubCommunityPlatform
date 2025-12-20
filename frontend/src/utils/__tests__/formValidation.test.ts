/**
 * Form Validation Utilities Tests
 *
 * Comprehensive tests for form validation utilities covering:
 * - Server error mapping
 * - Field error extraction
 * - Error application to forms
 */

import { describe, it, expect, vi } from 'vitest'
import { ValidationException } from '@/lib/api/exceptions'
import { AxiosError } from 'axios'
import {
  mapServerErrorsToFormErrors,
  applyServerErrorsToForm,
  getFieldError,
  hasFormErrors,
  getAllFormErrors,
} from '../formValidation'

// Mock react-hook-form
const createMockForm = () => {
  const errors: Record<string, any> = {}
  const values: Record<string, any> = {}

  return {
    setError: vi.fn((field: string, error: any) => {
      errors[field] = error
    }),
    clearErrors: vi.fn(() => {
      Object.keys(errors).forEach((key) => delete errors[key])
    }),
    getValues: vi.fn(() => values),
    setValue: vi.fn((field: string, value: any, options?: any) => {
      values[field] = value
    }),
    formState: {
      errors,
    },
  } as any
}

describe('formValidation utilities', () => {
  describe('mapServerErrorsToFormErrors', () => {
    it('should map ValidationException field errors', () => {
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
        { field: 'password', message: 'Password too short', code: 'VALIDATION_ERROR' },
      ])

      const result = mapServerErrorsToFormErrors(error)

      expect(result).toEqual({
        email: { message: 'Invalid email', type: 'VALIDATION_ERROR' },
        password: { message: 'Password too short', type: 'VALIDATION_ERROR' },
      })
    })

    it('should map AxiosError validation errors (DRF format)', () => {
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          email: ['Invalid email format'],
          password: ['Password must be at least 8 characters'],
          non_field_errors: ['General form error'],
        },
      }

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({
        email: { message: 'Invalid email format', type: 'validation' },
        password: { message: 'Password must be at least 8 characters', type: 'validation' },
        __non_field_errors__: { message: 'General form error', type: 'validation' },
      })
    })

    it('should handle single error string in DRF format', () => {
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          email: 'Invalid email',
        },
      }

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({
        email: { message: 'Invalid email', type: 'validation' },
      })
    })

    it('should return empty object for non-validation errors', () => {
      const error = new Error('Generic error')
      const result = mapServerErrorsToFormErrors(error)

      expect(result).toEqual({})
    })

    it('should handle ValidationException with no field errors', () => {
      const error = new ValidationException('Validation failed', [])
      const result = mapServerErrorsToFormErrors(error)

      expect(result).toEqual({})
    })

    it('should handle ValidationException with undefined field errors', () => {
      const error = new ValidationException('Validation failed', undefined)
      const result = mapServerErrorsToFormErrors(error)

      expect(result).toEqual({})
    })

    it('should handle AxiosError with non-400 status', () => {
      const axiosError = {
        response: {
          status: 500,
          data: { message: 'Server error' },
        },
      } as AxiosError

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({})
    })

    it('should handle AxiosError with no response', () => {
      const axiosError = {
        message: 'Network error',
      } as AxiosError

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({})
    })

    it('should handle AxiosError with non-object response data', () => {
      const axiosError = {
        response: {
          status: 400,
          data: 'String error message',
        },
      } as AxiosError

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({})
    })

    it('should handle AxiosError with null response data', () => {
      const axiosError = {
        response: {
          status: 400,
          data: null,
        },
      } as AxiosError

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({})
    })

    it('should handle multiple errors in array for same field', () => {
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          email: ['Error 1', 'Error 2', 'Error 3'],
        },
      }

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result).toEqual({
        email: { message: 'Error 1', type: 'validation' },
      })
    })

    it('should handle non-string error values in array', () => {
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          email: [{ message: 'Error object' }],
        },
      }

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result.email).toBeDefined()
      expect(result.email?.message).toBe('[object Object]')
    })

    it('should handle non-field errors as array', () => {
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          non_field_errors: ['Error 1', 'Error 2'],
        },
      }

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result.__non_field_errors__).toEqual({
        message: 'Error 1',
        type: 'validation',
      })
    })

    it('should handle non-field errors as string', () => {
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          non_field_errors: 'Single error',
        },
      }

      const result = mapServerErrorsToFormErrors(axiosError)

      expect(result.__non_field_errors__).toEqual({
        message: 'Single error',
        type: 'validation',
      })
    })

    it('should handle field errors with code from ValidationException', () => {
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'CUSTOM_CODE' },
      ])

      const result = mapServerErrorsToFormErrors(error)

      expect(result).toEqual({
        email: { message: 'Invalid email', type: 'CUSTOM_CODE' },
      })
    })

    it('should handle field errors without code from ValidationException', () => {
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: '' },
      ])

      const result = mapServerErrorsToFormErrors(error)

      // Empty code defaults to 'validation' type in the implementation
      expect(result).toEqual({
        email: { message: 'Invalid email', type: 'validation' },
      })
    })
  })

  describe('applyServerErrorsToForm', () => {
    it('should apply ValidationException errors to form', () => {
      const form = createMockForm()
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
      ])

      applyServerErrorsToForm(form, error)

      expect(form.setError).toHaveBeenCalledWith('email', {
        message: 'Invalid email',
        type: 'VALIDATION_ERROR',
      })
    })

    it('should call onNonFieldError for non-field errors', () => {
      const form = createMockForm()
      const onNonFieldError = vi.fn()
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          non_field_errors: ['General form error'],
        },
      }

      applyServerErrorsToForm(form, axiosError, { onNonFieldError })

      expect(onNonFieldError).toHaveBeenCalledWith('General form error')
    })

    it('should mark fields as touched when markFieldsAsTouched is true', () => {
      const form = createMockForm()
      const values = { email: 'test@example.com' }
      form.getValues = vi.fn(() => values)
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
      ])

      applyServerErrorsToForm(form, error, { markFieldsAsTouched: true })

      expect(form.setValue).toHaveBeenCalledWith('email', values, { shouldTouch: true })
    })

    it('should not mark fields as touched when markFieldsAsTouched is false', () => {
      const form = createMockForm()
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
      ])

      applyServerErrorsToForm(form, error, { markFieldsAsTouched: false })

      expect(form.setValue).not.toHaveBeenCalled()
    })

    it('should mark fields as touched by default', () => {
      const form = createMockForm()
      form.getValues = vi.fn(() => ({ email: 'test@example.com' }))
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
      ])

      applyServerErrorsToForm(form, error)

      expect(form.setValue).toHaveBeenCalled()
    })

    it('should apply multiple field errors', () => {
      const form = createMockForm()
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
        { field: 'password', message: 'Password too short', code: 'VALIDATION_ERROR' },
        { field: 'username', message: 'Username required', code: 'VALIDATION_ERROR' },
      ])

      applyServerErrorsToForm(form, error)

      expect(form.setError).toHaveBeenCalledTimes(3)
      expect(form.setError).toHaveBeenCalledWith('email', {
        message: 'Invalid email',
        type: 'VALIDATION_ERROR',
      })
      expect(form.setError).toHaveBeenCalledWith('password', {
        message: 'Password too short',
        type: 'VALIDATION_ERROR',
      })
      expect(form.setError).toHaveBeenCalledWith('username', {
        message: 'Username required',
        type: 'VALIDATION_ERROR',
      })
    })

    it('should not call onNonFieldError when no non-field errors', () => {
      const form = createMockForm()
      const onNonFieldError = vi.fn()
      const error = new ValidationException('Validation failed', [
        { field: 'email', message: 'Invalid email', code: 'VALIDATION_ERROR' },
      ])

      applyServerErrorsToForm(form, error, { onNonFieldError })

      expect(onNonFieldError).not.toHaveBeenCalled()
    })

    it('should not call onNonFieldError when callback not provided', () => {
      const form = createMockForm()
      const axiosError = {
        response: {
          status: 400,
          data: {
            non_field_errors: ['General form error'],
          },
        },
      } as AxiosError

      expect(() => {
        applyServerErrorsToForm(form, axiosError)
      }).not.toThrow()
    })

    it('should handle AxiosError validation errors', () => {
      const form = createMockForm()
      form.getValues = vi.fn(() => ({ email: 'test@example.com' }))
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          email: ['Invalid email format'],
          password: ['Password must be at least 8 characters'],
        },
      }

      applyServerErrorsToForm(form, axiosError)

      expect(form.setError).toHaveBeenCalledWith('email', {
        message: 'Invalid email format',
        type: 'validation',
      })
      expect(form.setError).toHaveBeenCalledWith('password', {
        message: 'Password must be at least 8 characters',
        type: 'validation',
      })
    })

    it('should not apply non-field errors as field errors', () => {
      const form = createMockForm()
      const axiosError = new AxiosError('Validation failed')
      axiosError.response = {
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as any,
        data: {
          non_field_errors: ['General form error'],
        },
      }

      applyServerErrorsToForm(form, axiosError)

      expect(form.setError).not.toHaveBeenCalledWith('__non_field_errors__', expect.anything())
    })
  })

  describe('getFieldError', () => {
    it('should return error message for field', () => {
      const errors = {
        email: { message: 'Invalid email', type: 'validation' },
      }

      const result = getFieldError(errors, 'email')

      expect(result).toBe('Invalid email')
    })

    it('should return undefined if field has no error', () => {
      const errors = {}

      const result = getFieldError(errors, 'email')

      expect(result).toBeUndefined()
    })

    it('should return undefined if error object has no message', () => {
      const errors = {
        email: { type: 'validation' },
      }

      const result = getFieldError(errors, 'email')

      expect(result).toBeUndefined()
    })

    it('should return undefined if error is not an object', () => {
      const errors = {
        email: 'string error',
      }

      const result = getFieldError(errors, 'email')

      expect(result).toBeUndefined()
    })

    it('should return undefined if error is null', () => {
      const errors = {
        email: null,
      }

      const result = getFieldError(errors, 'email')

      expect(result).toBeUndefined()
    })

    it('should handle error with empty message', () => {
      const errors = {
        email: { message: '', type: 'validation' },
      }

      const result = getFieldError(errors, 'email')

      expect(result).toBe('')
    })
  })

  describe('hasFormErrors', () => {
    it('should return true when form has errors', () => {
      const errors = {
        email: { message: 'Invalid email' },
      }

      expect(hasFormErrors(errors)).toBe(true)
    })

    it('should return false when form has no errors', () => {
      const errors = {}

      expect(hasFormErrors(errors)).toBe(false)
    })
  })

  describe('getAllFormErrors', () => {
    it('should return all form errors as array', () => {
      const errors = {
        email: { message: 'Invalid email' },
        password: { message: 'Password too short' },
      }

      const result = getAllFormErrors(errors)

      expect(result).toEqual([
        { field: 'email', message: 'Invalid email' },
        { field: 'password', message: 'Password too short' },
      ])
    })

    it('should return empty array when form has no errors', () => {
      const errors = {}

      const result = getAllFormErrors(errors)

      expect(result).toEqual([])
    })

    it('should skip errors without message property', () => {
      const errors = {
        email: { message: 'Invalid email' },
        password: { type: 'validation' },
        username: null,
      }

      const result = getAllFormErrors(errors)

      expect(result).toEqual([
        { field: 'email', message: 'Invalid email' },
      ])
    })

    it('should handle errors with empty message', () => {
      const errors = {
        email: { message: '' },
      }

      const result = getAllFormErrors(errors)

      expect(result).toEqual([
        { field: 'email', message: '' },
      ])
    })

    it('should handle many errors', () => {
      const errors = {
        field1: { message: 'Error 1' },
        field2: { message: 'Error 2' },
        field3: { message: 'Error 3' },
        field4: { message: 'Error 4' },
        field5: { message: 'Error 5' },
      }

      const result = getAllFormErrors(errors)

      expect(result).toHaveLength(5)
      expect(result.map(e => e.field)).toEqual(['field1', 'field2', 'field3', 'field4', 'field5'])
    })

    it('should preserve field names exactly', () => {
      const errors = {
        'field-name': { message: 'Error with dash' },
        'field_name': { message: 'Error with underscore' },
        'fieldName': { message: 'Error camelCase' },
      }

      const result = getAllFormErrors(errors)

      expect(result).toEqual([
        { field: 'field-name', message: 'Error with dash' },
        { field: 'field_name', message: 'Error with underscore' },
        { field: 'fieldName', message: 'Error camelCase' },
      ])
    })
  })
})

