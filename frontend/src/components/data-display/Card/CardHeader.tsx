import React from 'react'
import { cn } from '@/components/utils'
import { spacing } from '@/styles/tokens'

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Title
   */
  title?: string
  /**
   * Subtitle
   */
  subtitle?: string
  /**
   * Action buttons
   */
  actions?: React.ReactNode
  children?: React.ReactNode
}

/**
 * CardHeader component for card headers
 */
export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  actions,
  children,
  className,
  ...props
}) => {
  return (
    <div
      className={cn('card-header', className)}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: spacing[4],
        ...props.style,
      }}
      {...props}
    >
      <div>
        {title && (
          <div
            style={{
              fontSize: '18px',
              fontWeight: 500,
              marginBottom: subtitle ? spacing[1] : 0,
            }}
          >
            {title}
          </div>
        )}
        {subtitle && (
          <div style={{ fontSize: '14px', color: '#666' }}>{subtitle}</div>
        )}
        {children}
      </div>
      {actions && (
        <div style={{ display: 'flex', gap: spacing[2] }}>{actions}</div>
      )}
    </div>
  )
}

CardHeader.displayName = 'CardHeader'

