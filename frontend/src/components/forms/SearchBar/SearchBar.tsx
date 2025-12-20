import React, { useState } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface SearchBarProps {
  /**
   * Current search value
   */
  value: string
  /**
   * Callback when search value changes
   */
  onChange: (value: string) => void
  /**
   * Placeholder text
   * @default 'Search...'
   */
  placeholder?: string
  /**
   * Callback when search is submitted (Enter key)
   */
  onSubmit?: (value: string) => void
  /**
   * Show clear button
   * @default true
   */
  showClear?: boolean
  /**
   * Additional filter controls
   */
  filters?: React.ReactNode
  /**
   * Search suggestions (for autocomplete)
   */
  suggestions?: string[]
  className?: string
}

/**
 * SearchBar component for search input with filters
 */
export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = 'Search...',
  onSubmit,
  showClear = true,
  filters,
  suggestions = [],
  className,
}) => {
  const [isFocused, setIsFocused] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)

  const filteredSuggestions = suggestions.filter((s) =>
    s.toLowerCase().includes(value.toLowerCase())
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit?.(value)
  }

  const handleClear = () => {
    onChange('')
  }

  return (
    <div className={cn('search-bar', className)}>
      <form onSubmit={handleSubmit} style={{ position: 'relative' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing[2],
            border: `1px solid ${
              isFocused
                ? colors.primary[500]
                : colors.semantic.borderDefault
            }`,
            borderRadius: borderRadius.md,
            padding: `0 ${spacing[3]}px`,
            background: colors.semantic.backgroundDefault,
            transition: 'all 0.2s',
          }}
        >
          <span style={{ color: colors.semantic.textSecondary }}>🔍</span>
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onFocus={() => {
              setIsFocused(true)
              setShowSuggestions(true)
            }}
            onBlur={() => {
              setIsFocused(false)
              // Delay to allow suggestion clicks
              setTimeout(() => setShowSuggestions(false), 200)
            }}
            placeholder={placeholder}
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              padding: spacing[3],
              fontSize: '16px',
              background: 'transparent',
              color: colors.semantic.textPrimary,
            }}
          />
          {showClear && value && (
            <button
              type="button"
              onClick={handleClear}
              aria-label="Clear search"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: spacing[1],
                color: colors.semantic.textSecondary,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ✕
            </button>
          )}
          {onSubmit && (
            <button
              type="submit"
              aria-label="Search"
              style={{
                background: colors.primary[500],
                border: 'none',
                borderRadius: borderRadius.md,
                padding: `${spacing[2]}px ${spacing[4]}px`,
                color: '#FFFFFF',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 500,
              }}
            >
              Search
            </button>
          )}
        </div>
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
            {filteredSuggestions.map((suggestion, index) => (
              <div
                key={index}
                onClick={() => {
                  onChange(suggestion)
                  setShowSuggestions(false)
                }}
                style={{
                  padding: spacing[3],
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
      </form>
      {filters && (
        <div
          style={{
            marginTop: spacing[2],
            display: 'flex',
            alignItems: 'center',
            gap: spacing[2],
            flexWrap: 'wrap',
          }}
        >
          {filters}
        </div>
      )}
    </div>
  )
}

SearchBar.displayName = 'SearchBar'

