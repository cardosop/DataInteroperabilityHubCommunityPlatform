import React from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface TimePickerProps {
  /**
   * Label for the time picker
   */
  label?: string
  /**
   * Selected time (HH:mm format)
   */
  value: string | null
  /**
   * Callback when time changes
   */
  onChange: (time: string | null) => void
  /**
   * Time format
   * @default '24h'
   */
  format?: '12h' | '24h'
  /**
   * Error message
   */
  error?: string | null
  /**
   * Whether the field is required
   */
  required?: boolean
  /**
   * Whether the field is disabled
   */
  disabled?: boolean
  className?: string
}

/**
 * TimePicker component for time selection
 */
export const TimePicker: React.FC<TimePickerProps> = ({
  label,
  value,
  onChange,
  format = '24h',
  error,
  required,
  disabled,
  className,
}) => {
  const timePickerId = useId('time-picker')

  return (
    <div className={cn('time-picker', className)}>
      {label && (
        <label
          htmlFor={timePickerId}
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
        id={timePickerId}
        type="time"
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled}
        required={required}
        step={format === '24h' ? undefined : '1'}
        style={{
          width: '100%',
          height: '56px',
          padding: `0 ${spacing[4]}px`,
          fontSize: '16px',
          border: `1px solid ${
            error ? colors.error[500] : colors.semantic.borderDefault
          }`,
          borderRadius: borderRadius.md,
          background: disabled
            ? colors.semantic.actionDisabledBackground
            : colors.semantic.backgroundDefault,
          color: disabled
            ? colors.semantic.textDisabled
            : colors.semantic.textPrimary,
          outline: 'none',
          transition: 'all 0.2s',
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
      />
      {error && (
        <div
          role="alert"
          style={{
            marginTop: spacing[1],
            fontSize: '12px',
            color: colors.error[500],
          }}
        >
          {error}
        </div>
      )}
    </div>
  )
}

TimePicker.displayName = 'TimePicker'

