import React, { useRef, useEffect } from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { FormFieldError } from '../FormFieldError'

export interface TextareaProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange'> {
  /**
   * Label for the textarea
   */
  label?: string
  /**
   * Error message
   */
  error?: string | null
  /**
   * Helper text
   */
  helperText?: string
  /**
   * Number of rows (default if autoResize is false)
   * @default 4
   */
  rows?: number
  /**
   * Whether to auto-resize based on content
   * @default false
   */
  autoResize?: boolean
  /**
   * Show character count
   * @default false
   */
  showCharacterCount?: boolean
  /**
   * Maximum character count
   */
  maxLength?: number
  /**
   * Whether the field is required
   */
  required?: boolean
  /**
   * Callback when value changes
   */
  onChange?: (value: string) => void
}

/**
 * Textarea component for multi-line text input
 */
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      error,
      helperText,
      rows = 4,
      autoResize = false,
      showCharacterCount = false,
      maxLength,
      required,
      onChange,
      className,
      id,
      disabled,
      value,
      ...props
    },
    ref
  ) => {
    const textareaId = useId('textarea')
    const finalId = id || textareaId
    const errorId = `${finalId}-error`
    const helperId = `${finalId}-helper`
    const internalRef = useRef<HTMLTextAreaElement>(null)
    const textareaRef = (ref as React.RefObject<HTMLTextAreaElement>) || internalRef

    useEffect(() => {
      if (autoResize && textareaRef.current) {
        textareaRef.current.style.height = 'auto'
        textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
      }
    }, [value, autoResize])

    const currentLength = typeof value === 'string' ? value.length : 0

    return (
      <div className={cn('textarea', className)}>
        {label && (
          <label
            htmlFor={finalId}
            style={{
              display: 'block',
              marginBottom: spacing[1],
              fontSize: '14px',
              fontWeight: 500,
              color: error
                ? colors.error[500]
                : colors.semantic.textPrimary,
            }}
          >
            {label}
            {required && (
              <span
                style={{ color: colors.error[500], marginLeft: spacing[1] }}
                aria-label="required"
              >
                *
              </span>
            )}
          </label>
        )}
        <textarea
          ref={textareaRef}
          id={finalId}
          rows={autoResize ? 1 : rows}
          disabled={disabled}
          required={required}
          maxLength={maxLength}
          value={value}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={
            error ? errorId : helperText ? helperId : undefined
          }
          onChange={(e) => {
            onChange?.(e.target.value)
            if (autoResize) {
              e.target.style.height = 'auto'
              e.target.style.height = `${e.target.scrollHeight}px`
            }
          }}
          style={{
            width: '100%',
            minHeight: autoResize ? 'auto' : `${rows * 24}px`,
            padding: spacing[3],
            fontSize: '16px',
            fontFamily: 'inherit',
            border: `1px solid ${
              error
                ? colors.error[500]
                : colors.semantic.borderDefault
            }`,
            borderRadius: borderRadius.md,
            background: disabled
              ? colors.semantic.actionDisabledBackground
              : colors.semantic.backgroundDefault,
            color: disabled
              ? colors.semantic.textDisabled
              : colors.semantic.textPrimary,
            outline: 'none',
            resize: autoResize ? 'none' : 'vertical',
            transition: 'all 0.2s',
            ...props.style,
          }}
          onFocus={(e) => {
            if (!disabled) {
              e.currentTarget.style.borderColor = error
                ? colors.error[500]
                : colors.primary[500]
              e.currentTarget.style.boxShadow = `0 0 0 2px ${
                error ? colors.error[50] : colors.primary[50]
              }`
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = error
              ? colors.error[500]
              : colors.semantic.borderDefault
            e.currentTarget.style.boxShadow = 'none'
          }}
          {...props}
        />
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: spacing[1],
          }}
        >
          {error && <FormFieldError message={error} fieldId={finalId} />}
          {helperText && !error && (
            <div
              id={helperId}
              style={{
                fontSize: '12px',
                color: colors.semantic.textSecondary,
              }}
            >
              {helperText}
            </div>
          )}
          {showCharacterCount && (
            <div
              style={{
                fontSize: '12px',
                color: maxLength && currentLength > maxLength
                  ? colors.error[500]
                  : colors.semantic.textSecondary,
                marginLeft: 'auto',
              }}
            >
              {currentLength}
              {maxLength && ` / ${maxLength}`}
            </div>
          )}
        </div>
      </div>
    )
  }
)

Textarea.displayName = 'Textarea'

