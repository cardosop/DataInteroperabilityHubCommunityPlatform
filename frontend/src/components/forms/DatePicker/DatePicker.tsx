import React from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface DatePickerProps {
  /**
   * Label for the date picker
   */
  label?: string
  /**
   * Selected date (ISO string or Date object)
   */
  value: string | Date | null
  /**
   * Callback when date changes
   */
  onChange: (date: string | null) => void
  /**
   * Minimum selectable date
   */
  min?: string
  /**
   * Maximum selectable date
   */
  max?: string
  /**
   * Whether to show range picker
   * @default false
   */
  range?: boolean
  /**
   * Range start date
   */
  rangeStart?: string | Date | null
  /**
   * Range end date
   */
  rangeEnd?: string | Date | null
  /**
   * Callback when range changes
   */
  onRangeChange?: (start: string | null, end: string | null) => void
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
 * DatePicker component for date selection
 */
export const DatePicker: React.FC<DatePickerProps> = ({
  label,
  value,
  onChange,
  min,
  max,
  range = false,
  rangeStart,
  rangeEnd,
  onRangeChange,
  error,
  required,
  disabled,
  className,
}) => {
  const datePickerId = useId('date-picker')
  const formatDate = (date: string | Date | null): string => {
    if (!date) return ''
    const d = typeof date === 'string' ? new Date(date) : date
    return d.toISOString().split('T')[0]
  }

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value || null)
  }

  const handleRangeStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onRangeChange?.(e.target.value || null, rangeEnd ? formatDate(rangeEnd) : null)
  }

  const handleRangeEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onRangeChange?.(rangeStart ? formatDate(rangeStart) : null, e.target.value || null)
  }

  if (range) {
    return (
      <div className={cn('date-picker', className)}>
        {label && (
          <div
            style={{
              marginBottom: spacing[2],
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
          </div>
        )}
        <div
          style={{
            display: 'flex',
            gap: spacing[2],
            alignItems: 'center',
          }}
        >
          <input
            type="date"
            value={rangeStart ? formatDate(rangeStart) : ''}
            onChange={handleRangeStartChange}
            min={min}
            max={rangeEnd ? formatDate(rangeEnd) : max}
            disabled={disabled}
            style={{
              flex: 1,
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
            }}
          />
          <span style={{ color: colors.semantic.textSecondary }}>to</span>
          <input
            type="date"
            value={rangeEnd ? formatDate(rangeEnd) : ''}
            onChange={handleRangeEndChange}
            min={rangeStart ? formatDate(rangeStart) : min}
            max={max}
            disabled={disabled}
            style={{
              flex: 1,
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
            }}
          />
        </div>
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

  return (
    <div className={cn('date-picker', className)}>
      {label && (
        <label
          htmlFor={datePickerId}
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
        id={datePickerId}
        type="date"
        value={value ? formatDate(value) : ''}
        onChange={handleDateChange}
        min={min}
        max={max}
        disabled={disabled}
        required={required}
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

DatePicker.displayName = 'DatePicker'

