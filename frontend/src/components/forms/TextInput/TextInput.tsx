import { cn, useId } from '@/components/utils'
import { borderRadius, colors, spacing } from '@/styles/tokens'
import React from 'react'
import { FormFieldError } from '../FormFieldError'

export interface TextInputProps extends Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  'onChange'
> {
  /**
   * Label for the input
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
   * Whether the field is required
   */
  required?: boolean
  /**
   * Callback when value changes
   * Supports both event-based (from react-hook-form register) and value-based callbacks
   */
  onChange?: ((value: string) => void) | ((event: React.ChangeEvent<HTMLInputElement>) => void)
}

/**
 * TextInput component for single-line text input
 */
export const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(
  ({ label, error, helperText, required, className, id, disabled, ...props }, ref) => {
    const inputId = useId('text-input')
    const finalId = id || inputId
    const errorId = `${finalId}-error`
    const helperId = `${finalId}-helper`

    // Extract onFocus, onChange, and style to control them explicitly
    // For react-hook-form: we should NOT extract onBlur, name, or ref
    // These need to be passed through directly via restProps to maintain react-hook-form's closure context
    // register() provides: name, onBlur, ref - these MUST stay in restProps
    // onChange needs special handling to support both value-based and event-based callbacks
    const {
      onFocus: propsOnFocus,
      onChange: propsOnChange,
      style: propsStyle,
      ...restProps
    } = props as any

    // Merge refs: register's ref (from react-hook-form) and component's ref prop
    // We need to check if restProps has a ref from register()
    const registerRef = (restProps as any).ref
    const mergedRef = React.useCallback(
      (node: HTMLInputElement | null) => {
        // Call register's ref if it exists (react-hook-form needs this)
        if (registerRef) {
          if (typeof registerRef === 'function') {
            registerRef(node)
          } else if (registerRef && 'current' in registerRef) {
            ;(registerRef as React.MutableRefObject<HTMLInputElement | null>).current = node
          }
        }
        // Call component's ref prop if it exists
        if (ref) {
          if (typeof ref === 'function') {
            ref(node)
          } else if (ref && 'current' in ref) {
            ;(ref as React.MutableRefObject<HTMLInputElement | null>).current = node
          }
        }
      },
      [registerRef, ref]
    )

    return (
      <div className={cn('text-input', className)}>
        {label && (
          <label
            htmlFor={finalId}
            style={{
              display: 'block',
              marginBottom: spacing[1],
              fontSize: '14px',
              fontWeight: 500,
              color: error ? colors.error[500] : colors.semantic.textPrimary,
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
        <input
          {...restProps}
          ref={registerRef ? mergedRef : ref}
          id={finalId}
          disabled={disabled}
          required={required}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          onChange={e => {
            const value = e.target.value
            // Support both value-based and event-based onChange callbacks
            if (propsOnChange) {
              if (typeof propsOnChange === 'function') {
                // Check if this is from react-hook-form by checking if name exists in restProps
                // react-hook-form's register() provides name, onChange, onBlur, ref
                // If name exists, the onChange should be event-based (react-hook-form pattern)
                const isFromReactHookForm = !!(restProps as any).name

                if (isFromReactHookForm) {
                  // From react-hook-form - call with event
                  ;(propsOnChange as (event: React.ChangeEvent<HTMLInputElement>) => void)(e)
                } else {
                  // Custom callback - try value-based first (as per type definition)
                  // Most custom callbacks expect just the value
                  try {
                    ;(propsOnChange as (value: string) => void)(value)
                  } catch {
                    // Fallback to event-based if value-based fails
                    ;(propsOnChange as (event: React.ChangeEvent<HTMLInputElement>) => void)(e)
                  }
                }
              }
            }
            // Also handle onChange from restProps (in case it's passed directly, not via props)
            // This is a fallback for edge cases
            const restOnChange = (restProps as any).onChange
            if (
              restOnChange &&
              restOnChange !== propsOnChange &&
              typeof restOnChange === 'function'
            ) {
              restOnChange(e)
            }
          }}
          onBlur={e => {
            // Call register's onBlur if it exists (from react-hook-form, in restProps)
            const registerOnBlur = (restProps as any).onBlur
            if (registerOnBlur) {
              registerOnBlur(e)
            }
            // Apply visual styling
            e.currentTarget.style.borderColor = error
              ? colors.error[500]
              : colors.semantic.borderDefault
            e.currentTarget.style.boxShadow = 'none'
          }}
          onFocus={e => {
            if (!disabled) {
              e.currentTarget.style.borderColor = error ? colors.error[500] : colors.primary[500]
              e.currentTarget.style.boxShadow = `0 0 0 2px ${
                error ? colors.error[50] : colors.primary[50]
              }`
              // Call the prop's onFocus if provided
              if (propsOnFocus) {
                propsOnFocus(e)
              }
            }
          }}
          style={{
            width: '100%',
            height: '56px',
            padding: `0 ${spacing[4]}px`,
            fontSize: '16px', // Prevents zoom on iOS
            border: `1px solid ${error ? colors.error[500] : colors.semantic.borderDefault}`,
            borderRadius: borderRadius.md,
            background: disabled
              ? colors.semantic.actionDisabledBackground
              : colors.semantic.backgroundDefault,
            color: disabled ? colors.semantic.textDisabled : colors.semantic.textPrimary,
            outline: 'none',
            transition: 'all 0.2s',
            ...propsStyle,
          }}
        />
        {error && <FormFieldError message={error} fieldId={finalId} />}
        {helperText && !error && (
          <div
            id={helperId}
            style={{
              marginTop: spacing[1],
              fontSize: '12px',
              color: colors.semantic.textSecondary,
            }}
          >
            {helperText}
          </div>
        )}
      </div>
    )
  }
)

TextInput.displayName = 'TextInput'
