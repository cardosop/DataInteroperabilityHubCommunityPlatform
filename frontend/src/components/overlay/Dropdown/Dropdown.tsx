import React from 'react'
import { Select, SelectProps } from '@/components/forms/Select'

/**
 * Dropdown component - alias for Select with search and multi-select
 */
export const Dropdown: React.FC<SelectProps> = (props) => {
  return <Select {...props} searchable />
}

Dropdown.displayName = 'Dropdown'

