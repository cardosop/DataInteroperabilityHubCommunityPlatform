/**
 * Form Validation Utilities
 *
 * Utilities for handling form validation, including server-side error mapping
 * and field-level error association.
 */

import type { FieldError } from '@/lib/api/exceptions'
import { ValidationException } from '@/lib/api/exceptions'
import type { FieldErrors, UseFormReturn } from 'react-hook-form'
import { FetchError } from '@/lib/api/fetch'

/**
 * Map server-side validation errors to react-hook-form format
 *
 * @param error - ValidationException or AxiosError
 * @returns Field errors in react-hook-form format
 *
 * @example
 * ```tsx
 * try {
 *   await submitForm(data)
 * } catch (error) {
 *   const fieldErrors = mapServerErrorsToFormErrors(error)
 *   form.setError('fieldName', { message: fieldErrors.fieldName })
 * }
 * ```
 */
export function mapServerErrorsToFormErrors<T extends Record<string, any>>(
  error: unknown
): Partial<Record<keyof T, { message: string; type?: string }>> {
  const fieldErrors: Partial<Record<keyof T, { message: string; type?: string }>> = {}

  // Handle ValidationException
  if (error instanceof ValidationException) {
    if (error.fieldErrors) {
      error.fieldErrors.forEach((fieldError) => {
        const fieldName = fieldError.field as keyof T
        fieldErrors[fieldName] = {
          message: fieldError.message,
          type: fieldError.code || 'validation',
        }
      })
    }
    return fieldErrors
  }

  // Handle FetchError with validation response
  if (error instanceof FetchError && error.response?.status === 400) {
    const responseData = error.response.data

    // Handle DRF-style validation errors
    if (responseData && typeof responseData === 'object') {
      // Field-specific errors
      Object.keys(responseData).forEach((field) => {
        if (field !== 'non_field_errors') {
          const errors = responseData[field]
          const errorMessages = Array.isArray(errors) ? errors : [errors]
          const firstError = errorMessages[0]

          if (firstError) {
            const fieldName = field as keyof T
            fieldErrors[fieldName] = {
              message: typeof firstError === 'string' ? firstError : String(firstError),
              type: 'validation',
            }
          }
        }
      })

      // Non-field errors (general form errors)
      if (responseData.non_field_errors) {
        const nonFieldErrors = Array.isArray(responseData.non_field_errors)
          ? responseData.non_field_errors
          : [responseData.non_field_errors]
        if (nonFieldErrors.length > 0) {
          // Store non-field errors in a special field
          fieldErrors['__non_field_errors__' as keyof T] = {
            message: nonFieldErrors[0],
            type: 'validation',
          }
        }
      }
    }
  }

  return fieldErrors
}

/**
 * Apply server-side errors to react-hook-form
 *
 * @param form - React Hook Form instance
 * @param error - ValidationException or AxiosError
 * @param options - Additional options
 *
 * @example
 * ```tsx
 * try {
 *   await submitForm(data)
 * } catch (error) {
 *   applyServerErrorsToForm(form, error, {
 *     onNonFieldError: (message) => {
 *       showToast(message, 'error')
 *     }
 *   })
 * }
 * ```
 */
export function applyServerErrorsToForm<T extends Record<string, any>>(
  form: UseFormReturn<T>,
  error: unknown,
  options?: {
    /**
     * Callback for non-field errors
     */
    onNonFieldError?: (message: string) => void
    /**
     * Whether to mark fields as touched
     * @default true
     */
    markFieldsAsTouched?: boolean
  }
): void {
  const { onNonFieldError, markFieldsAsTouched = true } = options || {}
  const fieldErrors = mapServerErrorsToFormErrors<T>(error)

  // Apply field errors
  Object.keys(fieldErrors).forEach((fieldName) => {
    const field = fieldName as keyof T
    const error = fieldErrors[field]

    if (error && fieldName !== '__non_field_errors__') {
      form.setError(field, {
        message: error.message,
        type: error.type,
      })

      // Mark field as touched if option is enabled
      if (markFieldsAsTouched) {
        form.setValue(field, form.getValues(field), { shouldTouch: true })
      }
    }
  })

  // Handle non-field errors
  const nonFieldError = fieldErrors['__non_field_errors__' as keyof T]
  if (nonFieldError && onNonFieldError) {
    onNonFieldError(nonFieldError.message)
  }
}

/**
 * Get field error message from form errors
 *
 * @param errors - Form errors from react-hook-form
 * @param fieldName - Field name
 * @returns Error message or undefined
 */
export function getFieldError<T extends Record<string, any>>(
  errors: FieldErrors<T>,
  fieldName: keyof T
): string | undefined {
  const error = errors[fieldName]
  if (!error) return undefined

  if (typeof error === 'object' && 'message' in error) {
    return error.message as string | undefined
  }

  return undefined
}

/**
 * Check if form has any errors
 *
 * @param errors - Form errors from react-hook-form
 * @returns True if form has errors
 */
export function hasFormErrors<T extends Record<string, any>>(
  errors: FieldErrors<T>
): boolean {
  return Object.keys(errors).length > 0
}

/**
 * Get all error messages from form
 *
 * @param errors - Form errors from react-hook-form
 * @returns Array of error messages with field names
 */
export function getAllFormErrors<T extends Record<string, any>>(
  errors: FieldErrors<T>
): Array<{ field: string; message: string }> {
  const errorList: Array<{ field: string; message: string }> = []

  Object.keys(errors).forEach((fieldName) => {
    const error = errors[fieldName as keyof T]
    if (error && typeof error === 'object' && 'message' in error) {
      errorList.push({
        field: fieldName,
        message: error.message as string,
      })
    }
  })

  return errorList
}

