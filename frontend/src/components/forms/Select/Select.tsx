import React, { useState, useRef, useEffect } from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps {
  /**
   * Label for the select
   */
  label?: string
  /**
   * Array of options
   */
  options: SelectOption[]
  /**
   * Selected value(s)
   */
  value: string | string[] | null
  /**
   * Callback when selection changes
   */
  onChange: (value: string | string[]) => void
  /**
   * Whether multiple selection is allowed
   * @default false
   */
  multiple?: boolean
  /**
   * Placeholder text
   */
  placeholder?: string
  /**
   * Whether to show search
   * @default false
   */
  searchable?: boolean
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
   * Whether the field is disabled
   */
  disabled?: boolean
  className?: string
}

/**
 * Select component for dropdown selection
 */
export const Select: React.FC<SelectProps> = ({
  label,
  options,
  value,
  onChange,
  multiple = false,
  placeholder = 'Select...',
  searchable = false,
  error,
  helperText,
  required,
  disabled,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const selectId = useId('select')
  const containerRef = useRef<HTMLDivElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const selectedValues = Array.isArray(value) ? value : value ? [value] : []
  const selectedOptions = options.filter((opt) =>
    selectedValues.includes(opt.value)
  )

  const filteredOptions = searchable
    ? options.filter((opt) =>
        opt.label.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : options

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
        setSearchTerm('')
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen)
      if (!isOpen) {
        setSearchTerm('')
      }
    }
  }

  const handleSelect = (optionValue: string) => {
    if (multiple) {
      const newValues = selectedValues.includes(optionValue)
        ? selectedValues.filter((v) => v !== optionValue)
        : [...selectedValues, optionValue]
      onChange(newValues)
    } else {
      onChange(optionValue)
      setIsOpen(false)
    }
  }

  const displayText = multiple
    ? selectedOptions.length > 0
      ? `${selectedOptions.length} selected`
      : placeholder
    : selectedOptions[0]?.label || placeholder

  return (
    <div ref={containerRef} className={cn('select', className)}>
      {label && (
        <label
          htmlFor={selectId}
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
      <div style={{ position: 'relative' }}>
        <button
          id={selectId}
          type="button"
          onClick={handleToggle}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          style={{
            width: '100%',
            height: '56px',
            padding: `0 ${spacing[4]}px`,
            fontSize: '16px',
            textAlign: 'left',
            border: `1px solid ${
              error ? colors.error[500] : colors.semantic.borderDefault
            }`,
            borderRadius: borderRadius.md,
            background: disabled
              ? colors.semantic.actionDisabledBackground
              : colors.semantic.backgroundDefault,
            color: disabled
              ? colors.semantic.textDisabled
              : selectedValues.length === 0
                ? colors.semantic.textHint
                : colors.semantic.textPrimary,
            cursor: disabled ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
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
        >
          <span>{displayText}</span>
          <span
            style={{
              transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s',
            }}
          >
            ▼
          </span>
        </button>
        {isOpen && (
          <div
            ref={dropdownRef}
            role="listbox"
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: spacing[1],
              background: colors.semantic.backgroundDefault,
              border: `1px solid ${colors.semantic.borderDefault}`,
              borderRadius: borderRadius.md,
              boxShadow: shadows.elevation4,
              maxHeight: '300px',
              overflowY: 'auto',
              zIndex: 1000,
            }}
          >
            {searchable && (
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search..."
                style={{
                  width: '100%',
                  padding: spacing[2],
                  border: 'none',
                  borderBottom: `1px solid ${colors.semantic.borderDivider}`,
                  outline: 'none',
                  fontSize: '14px',
                }}
                onClick={(e) => e.stopPropagation()}
              />
            )}
            {filteredOptions.length === 0 ? (
              <div
                style={{
                  padding: spacing[4],
                  textAlign: 'center',
                  color: colors.semantic.textSecondary,
                  fontSize: '14px',
                }}
              >
                No options found
              </div>
            ) : (
              filteredOptions.map((option) => {
                const isSelected = selectedValues.includes(option.value)
                return (
                  <div
                    key={option.value}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => !option.disabled && handleSelect(option.value)}
                    style={{
                      padding: spacing[3],
                      cursor: option.disabled ? 'not-allowed' : 'pointer',
                      background: isSelected
                        ? colors.primary[50]
                        : 'transparent',
                      color: option.disabled
                        ? colors.semantic.textDisabled
                        : colors.semantic.textPrimary,
                      fontSize: '14px',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      if (!option.disabled && !isSelected) {
                        e.currentTarget.style.background =
                          colors.semantic.actionHover
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = 'transparent'
                      }
                    }}
                  >
                    {multiple && (
                      <input
                        type="checkbox"
                        checked={isSelected}
                        readOnly
                        style={{
                          marginRight: spacing[2],
                          accentColor: colors.primary[500],
                        }}
                      />
                    )}
                    {option.label}
                  </div>
                )
              })
            )}
          </div>
        )}
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
      {helperText && !error && (
        <div
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

Select.displayName = 'Select'

