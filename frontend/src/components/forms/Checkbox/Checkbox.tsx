import React from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'type'> {
  /**
   * Label for the checkbox
   */
  label?: string
  /**
   * Whether the checkbox is checked
   */
  checked?: boolean
  /**
   * Callback when checked state changes
   */
  onChange?: (checked: boolean) => void
  /**
   * Whether the checkbox is indeterminate
   */
  indeterminate?: boolean
}

/**
 * Checkbox component for single checkbox input
 */
export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  (
    {
      label,
      checked = false,
      onChange,
      indeterminate = false,
      className,
      id,
      disabled,
      ...props
    },
    ref
  ) => {
    const checkboxId = useId('checkbox')
    const finalId = id || checkboxId
    const inputRef = React.useRef<HTMLInputElement>(null)

    React.useImperativeHandle(ref, () => inputRef.current!)

    React.useEffect(() => {
      if (inputRef.current) {
        inputRef.current.indeterminate = indeterminate
      }
    }, [indeterminate])

    return (
      <div
        className={cn('checkbox', className)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing[2],
        }}
      >
        <input
          ref={inputRef}
          id={finalId}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange?.(e.target.checked)}
          style={{
            width: '20px',
            height: '20px',
            cursor: disabled ? 'not-allowed' : 'pointer',
            accentColor: colors.primary[500],
            ...props.style,
          }}
          {...props}
        />
        {label && (
          <label
            htmlFor={finalId}
            style={{
              fontSize: '14px',
              color: disabled
                ? colors.semantic.textDisabled
                : colors.semantic.textPrimary,
              cursor: disabled ? 'not-allowed' : 'pointer',
              userSelect: 'none',
            }}
          >
            {label}
          </label>
        )}
      </div>
    )
  }
)

Checkbox.displayName = 'Checkbox'

