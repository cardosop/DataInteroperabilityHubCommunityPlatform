import React from 'react'
import { Select, SelectProps } from '../Select'

export interface MultiSelectProps extends Omit<SelectProps, 'multiple' | 'value' | 'onChange'> {
  /**
   * Selected values
   */
  value: string[]
  /**
   * Callback when selection changes
   */
  onChange: (values: string[]) => void
}

/**
 * MultiSelect component - wrapper around Select with multiple=true
 */
export const MultiSelect: React.FC<MultiSelectProps> = ({
  value,
  onChange,
  ...props
}) => {
  return (
    <Select
      {...props}
      multiple={true}
      value={value}
      onChange={onChange as (value: string | string[]) => void}
    />
  )
}

MultiSelect.displayName = 'MultiSelect'

