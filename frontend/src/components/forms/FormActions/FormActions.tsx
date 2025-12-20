/**
 * FormActions Component
 *
 * Standard form action buttons including submit, reset, and clear.
 * Provides consistent form action patterns.
 */

import React from 'react'
import { Box, Button, ButtonProps } from '@mui/material'
import { UseFormReturn, FieldValues } from 'react-hook-form'
import { spacing } from '@/styles/tokens'

export interface FormActionsProps<T extends FieldValues = FieldValues> {
  /**
   * React Hook Form instance
   */
  form: UseFormReturn<T>
  /**
   * Submit button label
   */
  submitLabel?: string
  /**
   * Reset button label
   */
  resetLabel?: string
  /**
   * Clear button label
   */
  clearLabel?: string
  /**
   * Show reset button
   */
  showReset?: boolean
  /**
   * Show clear button
   */
  showClear?: boolean
  /**
   * Loading state
   */
  loading?: boolean
  /**
   * Disabled state
   */
  disabled?: boolean
  /**
   * Submit button props
   */
  submitButtonProps?: ButtonProps
  /**
   * Reset button props
   */
  resetButtonProps?: ButtonProps
  /**
   * Clear button props
   */
  clearButtonProps?: ButtonProps
  /**
   * Callback when form is submitted
   */
  onSubmit?: (data: T) => void | Promise<void>
  /**
   * Callback when form is reset
   */
  onReset?: () => void
  /**
   * Callback when form is cleared
   */
  onClear?: () => void
  /**
   * Button alignment
   */
  align?: 'left' | 'center' | 'right' | 'space-between'
}

/**
 * FormActions component for form buttons
 */
export function FormActions<T extends FieldValues = FieldValues>({
  form,
  submitLabel = 'Submit',
  resetLabel = 'Reset',
  clearLabel = 'Clear',
  showReset = true,
  showClear = false,
  loading = false,
  disabled = false,
  submitButtonProps,
  resetButtonProps,
  clearButtonProps,
  onSubmit,
  onReset,
  onClear,
  align = 'right',
}: FormActionsProps<T>) {
  const { handleSubmit, reset, formState } = form

  const handleReset = () => {
    reset()
    onReset?.()
  }

  const handleClear = () => {
    reset(undefined, { keepDefaultValues: false })
    onClear?.()
  }

  const handleFormSubmit = async (data: T) => {
    if (onSubmit) {
      await onSubmit(data)
    }
  }

  const onSubmitHandler = handleSubmit(handleFormSubmit)

  const getAlignmentStyles = () => {
    switch (align) {
      case 'left':
        return { justifyContent: 'flex-start' }
      case 'center':
        return { justifyContent: 'center' }
      case 'right':
        return { justifyContent: 'flex-end' }
      case 'space-between':
        return { justifyContent: 'space-between' }
      default:
        return { justifyContent: 'flex-end' }
    }
  }

  return (
    <Box
      sx={{
        display: 'flex',
        gap: spacing[2],
        marginTop: spacing[4],
        paddingTop: spacing[4],
        borderTop: 1,
        borderColor: 'divider',
        ...getAlignmentStyles(),
      }}
    >
      {showClear && (
        <Button
          variant="outlined"
          onClick={handleClear}
          disabled={loading || disabled}
          {...clearButtonProps}
        >
          {clearLabel}
        </Button>
      )}
      {showReset && (
        <Button
          variant="outlined"
          onClick={handleReset}
          disabled={loading || disabled || !formState.isDirty}
          {...resetButtonProps}
        >
          {resetLabel}
        </Button>
      )}
      <Button
        type="submit"
        variant="contained"
        onClick={onSubmitHandler}
        disabled={loading || disabled || !formState.isValid}
        {...submitButtonProps}
      >
        {submitLabel}
      </Button>
    </Box>
  )
}

