import React from 'react'
import { cn } from '@/components/utils'
import { Checkbox, CheckboxProps } from './Checkbox'

export interface CheckboxOption {
  value: string
  label: string
  disabled?: boolean
}

export interface CheckboxGroupProps {
  /**
   * Array of checkbox options
   */
  options: CheckboxOption[]
  /**
   * Selected values
   */
  value: string[]
  /**
   * Callback when selection changes
   */
  onChange: (values: string[]) => void
  /**
   * Label for the group
   */
  label?: string
  /**
   * Whether to show "Select All" option
   * @default false
   */
  showSelectAll?: boolean
  /**
   * Layout direction
   * @default 'vertical'
   */
  direction?: 'horizontal' | 'vertical'
  className?: string
}

/**
 * CheckboxGroup component for multiple checkboxes
 */
export const CheckboxGroup: React.FC<CheckboxGroupProps> = ({
  options,
  value,
  onChange,
  label,
  showSelectAll = false,
  direction = 'vertical',
  className,
}) => {
  const allSelected = options.length > 0 && value.length === options.length
  const someSelected = value.length > 0 && value.length < options.length

  const handleSelectAll = () => {
    if (allSelected) {
      onChange([])
    } else {
      onChange(options.map((opt) => opt.value))
    }
  }

  const handleChange = (optionValue: string, checked: boolean) => {
    if (checked) {
      onChange([...value, optionValue])
    } else {
      onChange(value.filter((v) => v !== optionValue))
    }
  }

  return (
    <div className={cn('checkbox-group', className)}>
      {label && (
        <div
          style={{
            marginBottom: '8px',
            fontSize: '14px',
            fontWeight: 500,
          }}
        >
          {label}
        </div>
      )}
      {showSelectAll && (
        <Checkbox
          label="Select All"
          checked={allSelected}
          indeterminate={someSelected}
          onChange={handleSelectAll}
          style={{ marginBottom: '8px' }}
        />
      )}
      <div
        style={{
          display: 'flex',
          flexDirection: direction === 'vertical' ? 'column' : 'row',
          gap: '8px',
          flexWrap: direction === 'horizontal' ? 'wrap' : 'nowrap',
        }}
      >
        {options.map((option) => (
          <Checkbox
            key={option.value}
            label={option.label}
            checked={value.includes(option.value)}
            disabled={option.disabled}
            onChange={(checked) => handleChange(option.value, checked)}
          />
        ))}
      </div>
    </div>
  )
}

CheckboxGroup.displayName = 'CheckboxGroup'

