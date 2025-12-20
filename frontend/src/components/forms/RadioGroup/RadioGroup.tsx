import React from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface RadioOption {
  value: string
  label: string
  disabled?: boolean
}

export interface RadioGroupProps {
  /**
   * Array of radio options
   */
  options: RadioOption[]
  /**
   * Selected value
   */
  value: string | null
  /**
   * Callback when selection changes
   */
  onChange: (value: string) => void
  /**
   * Label for the group
   */
  label?: string
  /**
   * Layout direction
   * @default 'vertical'
   */
  direction?: 'horizontal' | 'vertical'
  /**
   * Name attribute for radio inputs (auto-generated if not provided)
   */
  name?: string
  className?: string
}

/**
 * RadioGroup component for radio button group
 */
export const RadioGroup: React.FC<RadioGroupProps> = ({
  options,
  value,
  onChange,
  label,
  direction = 'vertical',
  name,
  className,
}) => {
  const groupId = useId('radio-group')
  const groupName = name || groupId

  return (
    <div className={cn('radio-group', className)}>
      {label && (
        <div
          style={{
            marginBottom: spacing[2],
            fontSize: '14px',
            fontWeight: 500,
            color: colors.semantic.textPrimary,
          }}
        >
          {label}
        </div>
      )}
      <div
        role="radiogroup"
        aria-label={label}
        style={{
          display: 'flex',
          flexDirection: direction === 'vertical' ? 'column' : 'row',
          gap: spacing[3],
          flexWrap: direction === 'horizontal' ? 'wrap' : 'nowrap',
        }}
      >
        {options.map((option) => {
          const isSelected = value === option.value
          const optionId = `${groupId}-${option.value}`

          return (
            <label
              key={option.value}
              htmlFor={optionId}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: spacing[2],
                cursor: option.disabled ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                color: option.disabled
                  ? colors.semantic.textDisabled
                  : colors.semantic.textPrimary,
              }}
            >
              <input
                id={optionId}
                type="radio"
                name={groupName}
                value={option.value}
                checked={isSelected}
                disabled={option.disabled}
                onChange={() => !option.disabled && onChange(option.value)}
                style={{
                  width: '20px',
                  height: '20px',
                  cursor: option.disabled ? 'not-allowed' : 'pointer',
                  accentColor: colors.primary[500],
                }}
              />
              {option.label}
            </label>
          )
        })}
      </div>
    </div>
  )
}

RadioGroup.displayName = 'RadioGroup'

