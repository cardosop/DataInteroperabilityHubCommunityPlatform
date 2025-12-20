import React from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface SwitchProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'type'> {
  /**
   * Label for the switch
   */
  label?: string
  /**
   * Whether the switch is on
   */
  checked?: boolean
  /**
   * Callback when checked state changes
   */
  onChange?: (checked: boolean) => void
}

/**
 * Switch component for toggle input
 */
export const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  (
    { label, checked = false, onChange, className, id, disabled, ...props },
    ref
  ) => {
    const switchId = useId('switch')
    const finalId = id || switchId

    return (
      <div
        className={cn('switch', className)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing[2],
        }}
      >
        <label
          htmlFor={finalId}
          style={{
            position: 'relative',
            display: 'inline-block',
            width: '44px',
            height: '24px',
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          <input
            ref={ref}
            id={finalId}
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(e) => onChange?.(e.target.checked)}
            style={{
              opacity: 0,
              width: 0,
              height: 0,
            }}
            {...props}
          />
          <span
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: checked
                ? colors.primary[500]
                : colors.semantic.borderDefault,
              borderRadius: borderRadius.full,
              transition: 'background-color 0.2s',
              opacity: disabled ? 0.5 : 1,
            }}
          >
            <span
              style={{
                position: 'absolute',
                content: '""',
                height: '18px',
                width: '18px',
                left: checked ? '22px' : '3px',
                bottom: '3px',
                backgroundColor: '#FFFFFF',
                borderRadius: borderRadius.full,
                transition: 'left 0.2s',
                boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
              }}
            />
          </span>
        </label>
        {label && (
          <span
            style={{
              fontSize: '14px',
              color: disabled
                ? colors.semantic.textDisabled
                : colors.semantic.textPrimary,
              cursor: disabled ? 'not-allowed' : 'pointer',
              userSelect: 'none',
            }}
            onClick={() => !disabled && onChange?.(!checked)}
          >
            {label}
          </span>
        )}
      </div>
    )
  }
)

Switch.displayName = 'Switch'

