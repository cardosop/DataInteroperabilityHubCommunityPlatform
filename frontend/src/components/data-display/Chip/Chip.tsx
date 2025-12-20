import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface ChipProps {
  /**
   * Label text
   */
  label: string
  /**
   * Whether the chip is removable
   * @default false
   */
  removable?: boolean
  /**
   * Callback when chip is removed
   */
  onRemove?: () => void
  /**
   * Whether the chip is clickable
   * @default false
   */
  clickable?: boolean
  /**
   * Callback when chip is clicked
   */
  onClick?: () => void
  /**
   * Color variant
   * @default 'default'
   */
  color?: 'default' | 'primary' | 'success' | 'warning' | 'error'
  className?: string
}

const colorMap = {
  default: {
    bg: colors.gray[200],
    text: colors.gray[700],
    hover: colors.gray[300],
  },
  primary: {
    bg: colors.primary[100],
    text: colors.primary[700],
    hover: colors.primary[200],
  },
  success: {
    bg: colors.success[100],
    text: colors.success[700],
    hover: colors.success[200],
  },
  warning: {
    bg: colors.warning[100],
    text: colors.warning[700],
    hover: colors.warning[200],
  },
  error: {
    bg: colors.error[100],
    text: colors.error[700],
    hover: colors.error[200],
  },
} as const

/**
 * Chip component for removable/clickable tags
 */
export const Chip: React.FC<ChipProps> = ({
  label,
  removable = false,
  onRemove,
  clickable = false,
  onClick,
  color = 'default',
  className,
}) => {
  const chipColors = colorMap[color]

  return (
    <span
      className={cn('chip', `chip-${color}`, className)}
      onClick={clickable ? onClick : undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: spacing[1],
        padding: `${spacing[1]}px ${spacing[2]}px`,
        background: chipColors.bg,
        color: chipColors.text,
        borderRadius: borderRadius.full,
        fontSize: '12px',
        fontWeight: 500,
        cursor: clickable ? 'pointer' : removable ? 'default' : 'default',
        transition: 'background 0.2s',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        if (clickable || removable) {
          e.currentTarget.style.background = chipColors.hover
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = chipColors.bg
      }}
    >
      {label}
      {removable && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove?.()
          }}
          aria-label={`Remove ${label}`}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            marginLeft: spacing[1],
            fontSize: '16px',
            lineHeight: 1,
            color: chipColors.text,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          ×
        </button>
      )}
    </span>
  )
}

Chip.displayName = 'Chip'

