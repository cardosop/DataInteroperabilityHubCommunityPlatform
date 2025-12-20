/**
 * FormFieldError Component
 *
 * Component for displaying inline field validation errors.
 * Provides consistent error display with icon, red text, and accessibility support.
 */

import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface FormFieldErrorProps {
  /**
   * Error message to display
   */
  message: string
  /**
   * Field ID for aria-describedby association
   */
  fieldId?: string
  /**
   * Custom className
   */
  className?: string
  /**
   * Whether to show error icon
   * @default true
   */
  showIcon?: boolean
}

/**
 * FormFieldError component for displaying field validation errors
 */
export const FormFieldError: React.FC<FormFieldErrorProps> = ({
  message,
  fieldId,
  className,
  showIcon = true,
}) => {
  const errorId = fieldId ? `${fieldId}-error` : undefined

  return (
    <div
      id={errorId}
      role="alert"
      aria-live="polite"
      className={cn('form-field-error', className)}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: spacing[1],
        marginTop: spacing[1],
        fontSize: '12px',
        color: colors.error[500],
        lineHeight: 1.5,
      }}
    >
      {showIcon && (
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke={colors.error[500]}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            flexShrink: 0,
            marginTop: '2px',
          }}
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      )}
      <span>{message}</span>
    </div>
  )
}

FormFieldError.displayName = 'FormFieldError'

