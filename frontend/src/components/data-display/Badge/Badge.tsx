import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface BadgeProps {
  /**
   * Variant of the badge
   * @default 'neutral'
   */
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  /**
   * Size of the badge
   * @default 'md'
   */
  size?: 'sm' | 'md'
  children: React.ReactNode
  className?: string
}

const variantColors = {
  success: {
    bg: colors.success[100],
    text: colors.success[700],
  },
  warning: {
    bg: colors.warning[100],
    text: colors.warning[700],
  },
  error: {
    bg: colors.error[100],
    text: colors.error[700],
  },
  info: {
    bg: colors.info[100],
    text: colors.info[700],
  },
  neutral: {
    bg: colors.gray[200],
    text: colors.gray[700],
  },
} as const

/**
 * Badge component for status badges and labels
 */
export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  children,
  className,
}) => {
  const colors = variantColors[variant]
  const height = size === 'sm' ? '20px' : '24px'
  const fontSize = size === 'sm' ? '11px' : '12px'
  const padding = size === 'sm' ? `2px ${spacing[2]}px` : `4px ${spacing[2]}px`

  return (
    <span
      className={cn('badge', `badge-${variant}`, className)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        height,
        padding,
        fontSize,
        fontWeight: 500,
        background: colors.bg,
        color: colors.text,
        borderRadius: borderRadius.full,
        lineHeight: 1,
      }}
    >
      {children}
    </span>
  )
}

Badge.displayName = 'Badge'

