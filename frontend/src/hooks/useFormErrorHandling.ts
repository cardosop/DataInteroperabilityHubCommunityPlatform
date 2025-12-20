/**
 * useFormErrorHandling Hook
 *
 * Hook for comprehensive form error handling including:
 * - Server-side error mapping
 * - Error recovery (clear on field change)
 * - Scroll to first error
 * - Form error summary
 */

import { useEffect, useCallback, useRef, useState } from 'react'
import type { UseFormReturn, FieldErrors, FieldPath } from 'react-hook-form'
import { applyServerErrorsToForm, getAllFormErrors } from '@/utils/formValidation'

export interface UseFormErrorHandlingOptions<T extends Record<string, any>> {
  /**
   * React Hook Form instance
   */
  form: UseFormReturn<T>
  /**
   * Whether to enable error recovery (clear on field change)
   * @default true
   */
  enableErrorRecovery?: boolean
  /**
   * Whether to scroll to first error on validation failure
   * @default true
   */
  scrollToFirstError?: boolean
  /**
   * Scroll behavior
   * @default 'smooth'
   */
  scrollBehavior?: ScrollBehavior
  /**
   * Offset from top when scrolling to error
   * @default 100
   */
  scrollOffset?: number
  /**
   * Callback when non-field errors occur
   */
  onNonFieldError?: (message: string) => void
}

/**
 * Hook for comprehensive form error handling
 *
 * @param options - Configuration options
 * @returns Error handling utilities
 *
 * @example
 * ```tsx
 * function MyForm() {
 *   const form = useForm<FormData>()
 *   const { handleServerError, scrollToFirstError, errorSummary } = useFormErrorHandling({
 *     form,
 *     scrollToFirstError: true,
 *   })
 *
 *   const onSubmit = async (data: FormData) => {
 *     try {
 *       await submitForm(data)
 *     } catch (error) {
 *       handleServerError(error)
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={form.handleSubmit(onSubmit)}>
 *       {errorSummary && <FormErrorSummary errors={form.formState.errors} />}
 *       <!-- form fields -->
 *     </form>
 *   )
 * }
 * ```
 */
export function useFormErrorHandling<T extends Record<string, any>>(
  options: UseFormErrorHandlingOptions<T>
) {
  const {
    form,
    enableErrorRecovery = true,
    scrollToFirstError = true,
    scrollBehavior = 'smooth',
    scrollOffset = 100,
    onNonFieldError,
  } = options

  const { watch, formState, setError, clearErrors } = form
  const watchedValues = watch()
  const previousValuesRef = useRef<Partial<T>>({})
  const [hasScrolledToError, setHasScrolledToError] = useState(false)

  // Error recovery: clear errors when field value changes
  useEffect(() => {
    if (!enableErrorRecovery) return

    Object.keys(watchedValues).forEach((fieldName) => {
      const field = fieldName as FieldPath<T>
      const currentValue = watchedValues[field]
      const previousValue = previousValuesRef.current[field]

      // If value changed and field has an error, clear it
      if (
        currentValue !== previousValue &&
        previousValue !== undefined &&
        formState.errors[field]
      ) {
        clearErrors(field)
      }
    })

    // Update previous values
    previousValuesRef.current = { ...watchedValues }
  }, [watchedValues, enableErrorRecovery, formState.errors, clearErrors])

  /**
   * Handle server-side validation errors
   */
  const handleServerError = useCallback(
    (error: unknown) => {
      applyServerErrorsToForm(form, error, {
        onNonFieldError,
        markFieldsAsTouched: true,
      })

      // Scroll to first error after a short delay to allow DOM updates
      if (scrollToFirstError) {
        setTimeout(() => {
          scrollToFirstErrorField()
        }, 100)
      }
    },
    [form, onNonFieldError, scrollToFirstError]
  )

  /**
   * Scroll to first error field
   */
  const scrollToFirstErrorField = useCallback(() => {
    if (hasScrolledToError) return

    const errors = formState.errors
    const errorList = getAllFormErrors(errors)

    if (errorList.length === 0) return

    const firstErrorField = errorList[0].field

    // Try to find the field element
    // First, try by name attribute
    let fieldElement: HTMLElement | null = document.querySelector(
      `[name="${firstErrorField}"]`
    )

    // If not found, try by id
    if (!fieldElement) {
      fieldElement = document.getElementById(String(firstErrorField))
    }

    // If not found, try by data-field attribute
    if (!fieldElement) {
      fieldElement = document.querySelector(`[data-field="${firstErrorField}"]`)
    }

    // If still not found, try to find input/select/textarea with matching name
    if (!fieldElement) {
      const inputs = document.querySelectorAll('input, select, textarea')
      inputs.forEach((input) => {
        if (
          (input as HTMLElement).getAttribute('name') === firstErrorField ||
          (input as HTMLElement).id === firstErrorField
        ) {
          fieldElement = input as HTMLElement
        }
      })
    }

    if (fieldElement) {
      const elementTop = fieldElement.getBoundingClientRect().top + window.pageYOffset
      const offsetPosition = elementTop - scrollOffset

      window.scrollTo({
        top: offsetPosition,
        behavior: scrollBehavior,
      })

      // Focus the field for better accessibility
      if (fieldElement instanceof HTMLInputElement || fieldElement instanceof HTMLTextAreaElement) {
        fieldElement.focus()
      }

      setHasScrolledToError(true)
    }
  }, [formState.errors, scrollOffset, scrollBehavior, hasScrolledToError])

  /**
   * Manually trigger scroll to first error
   */
  const scrollToError = useCallback(() => {
    setHasScrolledToError(false)
    scrollToFirstErrorField()
  }, [scrollToFirstErrorField])

  /**
   * Clear all form errors
   */
  const clearAllErrors = useCallback(() => {
    clearErrors()
    setHasScrolledToError(false)
  }, [clearErrors])

  // Reset scroll flag when form is submitted successfully
  useEffect(() => {
    if (Object.keys(formState.errors).length === 0) {
      setHasScrolledToError(false)
    }
  }, [formState.errors])

  return {
    /**
     * Handle server-side validation errors
     */
    handleServerError,
    /**
     * Scroll to first error field
     */
    scrollToError,
    /**
     * Clear all form errors
     */
    clearAllErrors,
    /**
     * Whether form has errors
     */
    hasErrors: Object.keys(formState.errors).length > 0,
    /**
     * All form errors
     */
    errors: formState.errors,
    /**
     * Error summary data
     */
    errorSummary: getAllFormErrors(formState.errors),
  }
}

