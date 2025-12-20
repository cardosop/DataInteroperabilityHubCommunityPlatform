import React, { useState, KeyboardEvent } from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface TagInputProps {
  /**
   * Array of tags
   */
  value: string[]
  /**
   * Callback when tags change
   */
  onChange: (tags: string[]) => void
  /**
   * Placeholder text
   * @default 'Add tags...'
   */
  placeholder?: string
  /**
   * Autocomplete suggestions
   */
  suggestions?: string[]
  /**
   * Maximum number of tags
   */
  maxTags?: number
  /**
   * Validation function
   */
  validate?: (tag: string) => string | null
  /**
   * Label for the input
   */
  label?: string
  /**
   * Error message
   */
  error?: string | null
  className?: string
}

/**
 * TagInput component for adding/removing tags
 */
export const TagInput: React.FC<TagInputProps> = ({
  value,
  onChange,
  placeholder = 'Add tags...',
  suggestions = [],
  maxTags,
  validate,
  label,
  error,
  className,
}) => {
  const tagInputId = useId('tag-input')
  const [inputValue, setInputValue] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)

  const filteredSuggestions = suggestions.filter(
    (s) =>
      !value.includes(s) &&
      s.toLowerCase().includes(inputValue.toLowerCase())
  )

  const handleAddTag = (tag: string) => {
    const trimmedTag = tag.trim()
    if (!trimmedTag) return

    if (maxTags && value.length >= maxTags) return

    if (validate) {
      const validationError = validate(trimmedTag)
      if (validationError) {
        // In a real app, you'd show this error
        console.error(validationError)
        return
      }
    }

    if (!value.includes(trimmedTag)) {
      onChange([...value, trimmedTag])
    }
    setInputValue('')
    setShowSuggestions(false)
  }

  const handleRemoveTag = (tagToRemove: string) => {
    onChange(value.filter((tag) => tag !== tagToRemove))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      handleAddTag(inputValue)
    } else if (e.key === 'Backspace' && inputValue === '' && value.length > 0) {
      handleRemoveTag(value[value.length - 1])
    }
  }

  return (
    <div className={cn('tag-input', className)}>
      {label && (
        <label
          htmlFor={tagInputId}
          style={{
            display: 'block',
            marginBottom: spacing[1],
            fontSize: '14px',
            fontWeight: 500,
            color: error ? colors.error[500] : colors.semantic.textPrimary,
          }}
        >
          {label}
        </label>
      )}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: spacing[1],
          padding: spacing[2],
          border: `1px solid ${
            error ? colors.error[500] : colors.semantic.borderDefault
          }`,
          borderRadius: borderRadius.md,
          minHeight: '56px',
          background: colors.semantic.backgroundDefault,
          position: 'relative',
        }}
      >
        {value.map((tag) => (
          <span
            key={tag}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: spacing[1],
              padding: `${spacing[1]}px ${spacing[2]}px`,
              background: colors.primary[50],
              color: colors.primary[700],
              borderRadius: borderRadius.md,
              fontSize: '14px',
            }}
          >
            {tag}
            <button
              type="button"
              onClick={() => handleRemoveTag(tag)}
              aria-label={`Remove ${tag}`}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: colors.primary[700],
                padding: 0,
                marginLeft: spacing[1],
                fontSize: '16px',
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={tagInputId}
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value)
            setShowSuggestions(true)
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          placeholder={value.length === 0 ? placeholder : ''}
          style={{
            flex: 1,
            minWidth: '120px',
            border: 'none',
            outline: 'none',
            fontSize: '16px',
            background: 'transparent',
            color: colors.semantic.textPrimary,
          }}
        />
        {showSuggestions && filteredSuggestions.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: spacing[1],
              background: colors.semantic.backgroundDefault,
              border: `1px solid ${colors.semantic.borderDefault}`,
              borderRadius: borderRadius.md,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              zIndex: 1000,
              maxHeight: '200px',
              overflowY: 'auto',
            }}
          >
            {filteredSuggestions.map((suggestion) => (
              <div
                key={suggestion}
                onClick={() => handleAddTag(suggestion)}
                style={{
                  padding: spacing[2],
                  cursor: 'pointer',
                  fontSize: '14px',
                  color: colors.semantic.textPrimary,
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = colors.semantic.actionHover
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                }}
              >
                {suggestion}
              </div>
            ))}
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
    </div>
  )
}

TagInput.displayName = 'TagInput'

