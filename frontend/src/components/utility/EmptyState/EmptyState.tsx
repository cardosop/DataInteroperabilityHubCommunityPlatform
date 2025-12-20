import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface EmptyStateProps {
  /**
   * Illustration or icon
   */
  illustration?: React.ReactNode
  /**
   * Title text
   */
  title: string
  /**
   * Description text
   */
  description?: string
  /**
   * Call-to-action button
   */
  action?: React.ReactNode
  className?: string
}

/**
 * EmptyState component for empty states
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
  illustration,
  title,
  description,
  action,
  className,
}) => {
  return (
    <div
      className={cn('empty-state', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing[8],
        textAlign: 'center',
      }}
    >
      {illustration && (
        <div
          style={{
            fontSize: '64px',
            marginBottom: spacing[4],
            color: colors.semantic.textSecondary,
          }}
        >
          {illustration}
        </div>
      )}
      <h3
        style={{
          fontSize: '20px',
          fontWeight: 500,
          color: colors.semantic.textPrimary,
          margin: 0,
          marginBottom: spacing[2],
        }}
      >
        {title}
      </h3>
      {description && (
        <p
          style={{
            fontSize: '14px',
            color: colors.semantic.textSecondary,
            margin: 0,
            marginBottom: spacing[4],
            maxWidth: '400px',
          }}
        >
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  )
}

EmptyState.displayName = 'EmptyState'

