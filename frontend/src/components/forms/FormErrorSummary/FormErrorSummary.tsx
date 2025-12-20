/**
 * FormErrorSummary Component
 *
 * Component for displaying a summary of all form validation errors.
 * Typically displayed at the top of the form after submission attempt.
 */

import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import type { FieldErrors } from 'react-hook-form'
import { getAllFormErrors } from '@/utils/formValidation'

export interface FormErrorSummaryProps<T extends Record<string, any> = Record<string, any>> {
  /**
   * Form errors from react-hook-form
   */
  errors: FieldErrors<T>
  /**
   * Custom title
   * @default "Please correct the following errors:"
   */
  title?: string
  /**
   * Custom className
   */
  className?: string
  /**
   * Callback when error link is clicked (for scrolling to field)
   */
  onErrorClick?: (fieldName: string) => void
  /**
   * Whether to show error count
   * @default true
   */
  showCount?: boolean
}

/**
 * FormErrorSummary component for displaying form validation errors
 */
export function FormErrorSummary<T extends Record<string, any> = Record<string, any>>({
  errors,
  title = 'Please correct the following errors:',
  className,
  onErrorClick,
  showCount = true,
}: FormErrorSummaryProps<T>) {
  const errorList = getAllFormErrors(errors)

  if (errorList.length === 0) {
    return null
  }

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn('form-error-summary', className)}
      style={{
        padding: spacing[4],
        marginBottom: spacing[4],
        background: colors.error[50],
        border: `1px solid ${colors.error[200]}`,
        borderRadius: borderRadius.md,
        boxShadow: shadows.elevation1,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: spacing[2],
          marginBottom: spacing[2],
        }}
      >
        <svg
          width="20"
          height="20"
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
        <div style={{ flex: 1 }}>
          <h3
            style={{
              margin: 0,
              marginBottom: spacing[1],
              fontSize: '14px',
              fontWeight: 600,
              color: colors.error[700],
            }}
          >
            {title}
            {showCount && (
              <span
                style={{
                  marginLeft: spacing[1],
                  fontSize: '12px',
                  fontWeight: 400,
                  color: colors.error[600],
                }}
              >
                ({errorList.length} {errorList.length === 1 ? 'error' : 'errors'})
              </span>
            )}
          </h3>
          <ul
            style={{
              margin: 0,
              paddingLeft: spacing[5],
              listStyle: 'none',
            }}
          >
            {errorList.map((error, index) => (
              <li
                key={`${error.field}-${index}`}
                style={{
                  marginBottom: spacing[1],
                  fontSize: '13px',
                  color: colors.error[700],
                  lineHeight: 1.5,
                }}
              >
                {onErrorClick ? (
                  <button
                    type="button"
                    onClick={() => onErrorClick(error.field)}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      color: colors.error[700],
                      textDecoration: 'underline',
                      cursor: 'pointer',
                      fontSize: 'inherit',
                      fontFamily: 'inherit',
                      textAlign: 'left',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = colors.error[800]
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = colors.error[700]
                    }}
                  >
                    <strong>{error.field}:</strong> {error.message}
                  </button>
                ) : (
                  <>
                    <strong>{error.field}:</strong> {error.message}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

FormErrorSummary.displayName = 'FormErrorSummary'

