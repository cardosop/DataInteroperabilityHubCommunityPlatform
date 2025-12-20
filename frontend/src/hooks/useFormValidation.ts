/**
 * useFormValidation Hook
 *
 * Hook for inline form validation with blur and change events.
 * Integrates with react-hook-form and zod.
 */

import { useState, useCallback, useEffect } from 'react'
import { FieldErrors, UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

export interface UseFormValidationOptions<T> {
  /**
   * React Hook Form instance
   */
  form: UseFormReturn<T>
  /**
   * Zod schema for validation
   */
  schema?: z.ZodSchema<T>
  /**
   * Validate on blur (default: true)
   */
  validateOnBlur?: boolean
  /**
   * Validate on change (default: false)
   */
  validateOnChange?: boolean
  /**
   * Delay before validating on change (ms)
   */
  validateOnChangeDelay?: number
}

/**
 * Hook for inline form validation
 */
export function useFormValidation<T extends Record<string, unknown>>(
  options: UseFormValidationOptions<T>
) {
  const {
    form,
    schema,
    validateOnBlur = true,
    validateOnChange = false,
    validateOnChangeDelay = 500,
  } = options

  const [touchedFields, setTouchedFields] = useState<Set<string>>(new Set())
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<T>>({})

  const { formState, trigger, watch } = form

  // Update errors when form state changes
  useEffect(() => {
    setFieldErrors(formState.errors)
  }, [formState.errors])

  /**
   * Mark field as touched
   */
  const markFieldTouched = useCallback((fieldName: string) => {
    setTouchedFields((prev) => new Set([...prev, fieldName]))
  }, [])

  /**
   * Check if field should show error
   */
  const shouldShowError = useCallback(
    (fieldName: string): boolean => {
      return touchedFields.has(fieldName) && !!fieldErrors[fieldName]
    },
    [touchedFields, fieldErrors]
  )

  /**
   * Get error message for field
   */
  const getFieldError = useCallback(
    (fieldName: string): string | undefined => {
      if (!shouldShowError(fieldName)) return undefined
      const error = fieldErrors[fieldName]
      return error?.message as string | undefined
    },
    [shouldShowError, fieldErrors]
  )

  /**
   * Validate field on blur
   */
  const handleBlur = useCallback(
    async (fieldName: string) => {
      if (validateOnBlur) {
        markFieldTouched(fieldName)
        await trigger(fieldName as keyof T)
      }
    },
    [validateOnBlur, markFieldTouched, trigger]
  )

  /**
   * Validate field on change (with debounce)
   */
  const handleChange = useCallback(
    async (fieldName: string) => {
      if (validateOnChange) {
        markFieldTouched(fieldName)
        // Debounce validation
        const timeoutId = setTimeout(async () => {
          await trigger(fieldName as keyof T)
        }, validateOnChangeDelay)
        return () => clearTimeout(timeoutId)
      }
    },
    [validateOnChange, validateOnChangeDelay, markFieldTouched, trigger]
  )

  /**
   * Validate all fields
   */
  const validateAll = useCallback(async (): Promise<boolean> => {
    // Mark all fields as touched
    const allFields = Object.keys(watch())
    setTouchedFields(new Set(allFields))

    // Trigger validation
    const isValid = await trigger()
    return isValid
  }, [trigger, watch])

  /**
   * Clear all errors
   */
  const clearErrors = useCallback(() => {
    form.clearErrors()
    setTouchedFields(new Set())
    setFieldErrors({})
  }, [form])

  /**
   * Reset form and validation state
   */
  const reset = useCallback(
    (values?: T) => {
      form.reset(values)
      setTouchedFields(new Set())
      setFieldErrors({})
    },
    [form]
  )

  return {
    // State
    touchedFields,
    fieldErrors,
    formState,

    // Methods
    markFieldTouched,
    shouldShowError,
    getFieldError,
    handleBlur,
    handleChange,
    validateAll,
    clearErrors,
    reset,
  }
}

